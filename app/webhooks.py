"""
File: app/webhooks.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
WhatsApp webhook receiver and dispatcher.

Routing rule (LOCKED):
- Resolve the receiving WhatsApp Business number via payload metadata.phone_number_id
- Map that phone_number_id to an active WhatsAppNumber record
- If no active mapping exists, DO NOT RESPOND (prevents cross-bot leakage)
"""

import logging
import os
import re

from fastapi import APIRouter, Request, Response, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text as sql_text

from app.db import get_db
from app.handlers.admin_commands import handle_admin_command
from app.handlers.client_commands import handle_client_command
from app.handlers.media_handler import handle_media_message
from app.handlers.order_handler import handle_order_message
from app.models import WhatsAppNumber  # ✅ used for routing
from app.survey.survey_models import Survey, SurveyResponse
from app.survey.auto_close import auto_close_expired_surveys

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger("webhooks")
logging.basicConfig(level=logging.INFO)

ADMIN_ALLOWLIST = {
    n.strip()
    for n in os.getenv("OUTBOUND_TEST_ALLOWLIST", "").split(",")
    if n.strip()
}


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


def _extract_business_phone_number_id(payload: dict) -> str | None:
    """
    Returns the WhatsApp Business 'phone_number_id' from webhook metadata.

    This is the PRIMARY routing key for multi-bot setups.
    """
    try:
        return payload["entry"][0]["changes"][0]["value"]["metadata"]["phone_number_id"]
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


def _resolve_active_business_context(
    db: Session, business_phone_number_id: str | None
) -> tuple[str | None, str | None, str | None]:
    """
    Map WhatsApp Business phone_number_id -> (client_id, destination_number, phone_number_id)

    Returns:
      (client_id, business_destination_msisdn, phone_number_id)
    """
    if not business_phone_number_id:
        return None, None, None

    # NOTE:
    # We assume WhatsAppNumber has a phone_number_id column.
    # If yours is named differently, tell me the exact column name and I’ll adjust.
    wa = (
        db.query(WhatsAppNumber)
        .filter(WhatsAppNumber.status == "active")
        .filter(WhatsAppNumber.phone_number_id == business_phone_number_id)
        .first()
    )
    if not wa:
        return None, None, business_phone_number_id

    return wa.client_id, wa.destination_number, business_phone_number_id


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

    # -------------------------------
    # ROUTING KEY (receiving business number)
    # -------------------------------
    business_phone_number_id = _extract_business_phone_number_id(payload) or os.getenv(
        "META_WA_PHONE_NUMBER_ID"
    )

    # -------------------------------
    # AUTO-CLOSE SURVEYS (business-scoped)
    # -------------------------------
    if business_phone_number_id:
        auto_close_expired_surveys(db, business_phone_number_id)

    # -------------------------------
    # Resolve active business context
    # -------------------------------
    client_id, business_msisdn, resolved_phone_number_id = _resolve_active_business_context(
        db, business_phone_number_id
    )

    # If we cannot map this business number to an active client, DO NOT RESPOND.
    # This prevents cross-bot leakage (PilatesHQ getting KLResolute responses etc).
    if not client_id or not business_msisdn:
        logger.warning(
            "Ignoring message: no active WhatsAppNumber mapping for phone_number_id=%s",
            resolved_phone_number_id,
        )
        return Response(status_code=200)

    msg, sender_raw = _extract_message(payload)
    sender = _normalise_msisdn(sender_raw)

    if not msg or not sender:
        return Response(status_code=200)

    _upsert_client(db, sender)

    # -------------------------------
    # MEDIA (ADMIN IMAGES)
    # -------------------------------
    if handle_media_message(
        db=db,
        sender=sender,
        msg=msg,
        admin_allowlist=ADMIN_ALLOWLIST,
    ):
        return Response(status_code=200)

    # -------------------------------
    # INTERACTIVE (SURVEY ANSWERS)
    # -------------------------------
    if msg.get("type") == "interactive":
        reply = msg.get("interactive", {}).get("button_reply")
        if reply:
            survey = (
                db.query(Survey)
                .filter(Survey.status == "active")
                .order_by(Survey.started_at.desc())
                .first()
            )
            if survey:
                db.add(
                    SurveyResponse(
                        survey_id=survey.id,
                        client_number=sender,
                        button_id=reply.get("id"),
                        tag=reply.get("title"),
                    )
                )
                db.commit()
        return Response(status_code=200)

    # -------------------------------
    # TEXT
    # -------------------------------
    if msg.get("type") == "text":
        text = msg["text"]["body"].strip()

        # -------------------------------
        # ADMIN COMMANDS
        # -------------------------------
        if handle_admin_command(
            db=db,
            sender_number=sender,
            message_text=text,
            admin_allowlist=ADMIN_ALLOWLIST,
        ):
            return Response(status_code=200)

        # -------------------------------
        # ORDERS (Phase 1)
        # -------------------------------
        handled = handle_order_message(
            db=db,
            from_number=sender,
            text=text,
            context={"client_id": client_id, "business_msisdn": business_msisdn},
        )
        if handled:
            return Response(status_code=200)

        # -------------------------------
        # CLIENT COMMANDS (scoped to this business)
        # -------------------------------
        handle_client_command(
            db=db,
            sender_number=sender,
            message_text=text,
            msg=msg,
            resolved_client_id=client_id,
            resolved_business_number=business_msisdn,
            resolved_phone_number_id=resolved_phone_number_id,
        )

    return Response(status_code=200)
