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
from typing import Optional

from fastapi import APIRouter, Request, Response, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text as sql_text

from app.db import get_db
from app.models import WhatsAppNumber
from app.handlers.admin_commands import handle_admin_command
from app.handlers.client_commands import handle_client_command
from app.handlers.media_handler import handle_media_message
from app.handlers.galitos_order_handler import handle_order_message
from app.handlers.feedback_handler import handle_feedback_message
from app.survey.auto_close import auto_close_expired_surveys
from app.messaging.client_messenger import send_message

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger("webhooks")
logging.basicConfig(level=logging.INFO)

# -------------------------------------------------
# TEMPORARY GLOBAL FALLBACK (DO NOT REMOVE YET)
# -------------------------------------------------
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
        entry = payload.get("entry", [])
        if not entry:
            return None, None

        changes = entry[0].get("changes", [])
        if not changes:
            return None, None

        value = changes[0].get("value", {})
        messages = value.get("messages")

        if not messages:
            return None, None

        msg = messages[0]
        from_msisdn = msg.get("from")

        return msg, from_msisdn

    except Exception:
        logger.exception("EXTRACT_MESSAGE_FATAL_ERROR")
        return None, None


def _extract_business_msisdn(payload: dict) -> Optional[str]:
    try:
        raw = payload["entry"][0]["changes"][0]["value"]["metadata"]["display_phone_number"]
        return _normalise_msisdn(raw)
    except Exception:
        logger.warning("EXTRACT_BUSINESS_MSISDN_FAILED")
        return None


def _upsert_client(db: Session, client_number: str) -> None:
    logger.info("UPSERT_CLIENT | msisdn=%s", client_number)
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


def _resolve_business_context(db: Session, business_msisdn: Optional[str]):
    if not business_msisdn:
        logger.warning("NO_BUSINESS_MSISDN")
        return None, None

    wa = (
        db.query(WhatsAppNumber)
        .filter(WhatsAppNumber.destination_number == business_msisdn)
        .filter(WhatsAppNumber.status == "active")
        .first()
    )

    if not wa or not wa.klresolute_client_id:
        logger.warning("BUSINESS_CONTEXT_NOT_FOUND | msisdn=%s", business_msisdn)
        return None, None

    logger.info(
        "BUSINESS_CONTEXT_RESOLVED | client_id=%s | business_msisdn=%s",
        wa.klresolute_client_id,
        wa.destination_number,
    )
    return wa.klresolute_client_id, wa.destination_number


def _is_client_admin(db: Session, client_id: int, sender_msisdn: str) -> bool:
    row = db.execute(
        sql_text(
            """
            SELECT 1
            FROM klresolute_admin
            WHERE client_id = :client_id
              AND msisdn = :msisdn
              AND is_active = TRUE
            """
        ),
        {"client_id": client_id, "msisdn": sender_msisdn},
    ).first()

    if row:
        logger.info("ADMIN_MATCH_DB | client_id=%s | msisdn=%s", client_id, sender_msisdn)
        return True

    fallback = sender_msisdn in ADMIN_ALLOWLIST
    if fallback:
        logger.warning("ADMIN_MATCH_ALLOWLIST | msisdn=%s", sender_msisdn)
    return fallback


def _is_galitos_client(db: Session, client_id: int) -> bool:
    row = db.execute(
        sql_text(
            """
            SELECT 1
            FROM klresolute_client
            WHERE id = :id
              AND LOWER(name) = 'galitos'
              AND is_active = TRUE
            """
        ),
        {"id": client_id},
    ).first()

    return bool(row)


# -------------------------------------------------
# Webhook
# -------------------------------------------------

@router.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    logger.info("WEBHOOK_ENTER")

    try:
        payload = await request.json()
    except Exception:
        logger.exception("WEBHOOK_JSON_PARSE_FAILED")
        return Response(status_code=200)

    try:
        # --- Extract message & sender FIRST ---
        msg, sender_raw = _extract_message(payload)
        sender = _normalise_msisdn(sender_raw)

        if not msg or not sender:
            logger.warning("INVALID_MESSAGE_PAYLOAD")
            return Response(status_code=200)

        # -------------------------------------------------
        # PILATESHQ AUTORESPONSE (REMINDERS-ONLY NUMBER)
        # -------------------------------------------------
        business_phone_number_id = (
            payload.get("entry", [{}])[0]
                .get("changes", [{}])[0]
                .get("value", {})
                .get("metadata", {})
                .get("phone_number_id")
        )

        if business_phone_number_id == "926822817182737":
            send_message(
                to_number=sender,
                text=(
                    "Hi 👋 Thanks for your message.\n\n"
                    "This number is used for PilatesHQ class reminders only.\n"
                    "For bookings or questions, please WhatsApp Nadine on "
                    "0843131635 💜"
                ),
            )
            logger.info("PILATESHQ_AUTORESPONSE_SENT | sender=%s", sender)
            return Response(status_code=200)

        # --- Existing KLResolute logic BELOW (unchanged) ---

        business_msisdn = _extract_business_msisdn(payload)
        client_id, resolved_business_msisdn = _resolve_business_context(db, business_msisdn)

        if not client_id:
            logger.warning("NO_CLIENT_RESOLVED | ignoring message")
            return Response(status_code=200)

        auto_close_expired_surveys(db, resolved_business_msisdn)
        _upsert_client(db, sender)

        is_admin = _is_client_admin(db, client_id, sender)

        if handle_media_message(
            db=db,
            sender=sender,
            msg=msg,
            admin_allowlist=ADMIN_ALLOWLIST,
            client_id=client_id,
        ):
            return Response(status_code=200)

        if msg.get("type") == "interactive":
            handle_client_command(
                db=db,
                sender_number=sender,
                message_text="",
                msg=msg,
                resolved_client_id=client_id,
                resolved_business_number=resolved_business_msisdn,
            )
            return Response(status_code=200)

        if msg.get("type") == "text":
            text = (msg["text"]["body"] or "").strip()
            upper = text.upper()

            if is_admin and handle_admin_command(
                db=db,
                sender_number=sender,
                message_text=text,
                admin_allowlist=ADMIN_ALLOWLIST,
            ):
                return Response(status_code=200)

            if upper.startswith("FEEDBACK:"):
                handle_feedback_message(
                    db=db,
                    sender_number=sender,
                    message_text=text[len("FEEDBACK:"):].strip(),
                    media_id=None,
                    media_type=None,
                    client_id=client_id,
                    admin_numbers=ADMIN_ALLOWLIST,
                )
                return Response(status_code=200)

            if _is_galitos_client(db, client_id):
                if handle_order_message(
                    db=db,
                    from_number=sender,
                    text=text,
                    context={"client_id": client_id},
                ):
                    return Response(status_code=200)

            handle_client_command(
                db=db,
                sender_number=sender,
                message_text=text,
                msg=msg,
                resolved_client_id=client_id,
                resolved_business_number=resolved_business_msisdn,
            )

    except Exception:
        logger.exception("WEBHOOK_FATAL_ERROR")

    logger.info("WEBHOOK_EXIT")
    return Response(status_code=200)
