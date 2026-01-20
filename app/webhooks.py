from __future__ import annotations

"""
File: app/webhooks.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
WhatsApp webhook receiver and dispatcher.

ROUTING RULE (LOCKED):
- Route strictly by receiving WhatsApp business MSISDN
- Match against whatsapp_numbers.destination_number
- If no active match exists → DO NOT RESPOND
"""

import logging
import os
import re

from fastapi import APIRouter, Request, Response, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text as sql_text

from app.db import get_db
from app.models import WhatsAppNumber
from app.handlers.admin_commands import handle_admin_command
from app.handlers.client_commands import handle_client_command
from app.handlers.media_handler import handle_media_message
from app.handlers.order_handler import handle_order_message
from app.handlers.feedback_handler import handle_feedback_message
from app.survey.auto_close import auto_close_expired_surveys

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger("webhooks")
logging.basicConfig(level=logging.INFO)

ADMIN_ALLOWLIST = {
    n.strip()
    for n in os.getenv("OUTBOUND_TEST_ALLOWLIST", "").split(",")
    if n.strip()
}


# -------------------------------------------------
# Helpers
# -------------------------------------------------

def _normalise_msisdn(raw: str | None) -> str | None:
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("0"):
        digits = "27" + digits[1:]
    if digits.startswith("27") and len(digits) >= 11:
        return digits
    return None


def _extract_message(payload: dict):
    try:
        msg = payload["entry"][0]["changes"][0]["value"]["messages"][0]
        return msg, msg.get("from")
    except Exception:
        return None, None


def _extract_business_msisdn(payload: dict) -> str | None:
    try:
        raw = payload["entry"][0]["changes"][0]["value"]["metadata"]["display_phone_number"]
        return _normalise_msisdn(raw)
    except Exception:
        return None


def _upsert_client(db: Session, client_number: str) -> None:
    db.execute(
        sql_text(
            """
            INSERT INTO clients (client_number, last_interaction_at)
            VALUES (:client_number, now())
            ON CONFLICT (client_number)
            DO UPDATE SET
                last_interaction_at = now(),
                updated_at = now();
            """
        ),
        {"client_number": client_number},
    )
    db.commit()


def _resolve_business_context(db: Session, business_msisdn: str | None):
    if not business_msisdn:
        return None, None

    wa = (
        db.query(WhatsAppNumber)
        .filter(WhatsAppNumber.destination_number == business_msisdn)
        .filter(WhatsAppNumber.status == "active")
        .first()
    )

    if not wa:
        return None, None

    return wa.client_id, wa.destination_number


# -------------------------------------------------
# Webhook
# -------------------------------------------------

@router.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    logger.info("WhatsApp webhook received")

    try:
        payload = await request.json()
    except Exception:
        return Response(status_code=200)

    business_msisdn = _extract_business_msisdn(payload)
    client_id, resolved_business_msisdn = _resolve_business_context(db, business_msisdn)

    if not client_id:
        return Response(status_code=200)

    auto_close_expired_surveys(db, resolved_business_msisdn)

    msg, sender_raw = _extract_message(payload)
    sender = _normalise_msisdn(sender_raw)

    if not msg or not sender:
        return Response(status_code=200)

    _upsert_client(db, sender)

    # -------------------------------
    # Media (admin images → SPECIALS)
    # -------------------------------
    if handle_media_message(
        db=db,
        sender=sender,
        msg=msg,
        admin_allowlist=ADMIN_ALLOWLIST,
        client_id=client_id,   # ✅ REQUIRED
    ):
        return Response(status_code=200)

    # -------------------------------
    # Text
    # -------------------------------
    if msg.get("type") == "text":
        raw_text = msg["text"]["body"] or ""
        text = raw_text.strip()
        upper = text.upper()

        # Admin commands
        if handle_admin_command(
            db=db,
            sender_number=sender,
            message_text=text,
            admin_allowlist=ADMIN_ALLOWLIST,
        ):
            return Response(status_code=200)

        # FEEDBACK intent (explicit only)
        if upper.startswith("FEEDBACK:"):
            feedback_text = text[len("FEEDBACK:"):].strip()

            handle_feedback_message(
                db=db,
                sender_number=sender,
                message_text=feedback_text,
                media_id=None,
                media_type=None,
                client_id=client_id,
                admin_numbers=ADMIN_ALLOWLIST,
            )
            return Response(status_code=200)

        # Orders
        if handle_order_message(
            db=db,
            from_number=sender,
            text=text,
            context={"client_id": client_id},
        ):
            return Response(status_code=200)

        # Unknown → Client menu
        handle_client_command(
            db=db,
            sender_number=sender,
            message_text=text,
            msg=msg,
            resolved_client_id=client_id,
            resolved_business_number=resolved_business_msisdn,
        )

    return Response(status_code=200)
