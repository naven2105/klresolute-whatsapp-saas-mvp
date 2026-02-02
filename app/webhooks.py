from __future__ import annotations

"""
File: app/webhooks.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
WhatsApp webhook entry point.

GUARD RAILS (LOCKED):
- dispatch() is authoritative
- Once dispatch() runs, the message lifecycle MUST STOP
- Tier-1 must NEVER execute after dispatch()
- Extensive logging to make execution path explicit
"""

import logging
import re
from typing import Optional

from fastapi import APIRouter, Request, Response, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.db import get_db
from app.inbound_dispatcher import dispatch
from app.clients.magen.auto_close import auto_close_expired_inspections
from app.messaging.client_messenger import send_message

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger("webhooks")


# -------------------------------------------------
# Helpers
# -------------------------------------------------

def _normalise_msisdn(raw: str | None) -> Optional[str]:
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
        entry = payload["entry"][0]["changes"][0]["value"]

        messages = entry.get("messages")
        if not messages:
            logger.info("WEBHOOK_NON_MESSAGE_EVENT")
            return None, None, None, None

        msg = messages[0]
        sender = msg.get("from")
        provider_message_id = msg.get("id")
        business_raw = entry.get("metadata", {}).get("display_phone_number")

        logger.info(
            "WEBHOOK_MESSAGE_EXTRACTED | sender_raw=%s | business_raw=%s | provider_id=%s",
            sender,
            business_raw,
            provider_message_id,
        )

        return (
            msg,
            _normalise_msisdn(sender),
            _normalise_msisdn(business_raw),
            provider_message_id,
        )

    except Exception:
        logger.exception("WEBHOOK_PAYLOAD_PARSE_FAIL")
        return None, None, None, None


def _try_lock_provider_message(db: Session, provider_message_id: str) -> bool:
    if not provider_message_id:
        logger.warning("WEBHOOK_NO_PROVIDER_MESSAGE_ID | fail_open")
        return True

    try:
        result = db.execute(
            text(
                """
                INSERT INTO inbound_message_dedupe (provider_message_id)
                VALUES (:pid)
                ON CONFLICT (provider_message_id) DO NOTHING
                """
            ),
            {"pid": provider_message_id},
        )
        db.commit()

        inserted = bool(getattr(result, "rowcount", 0) == 1)
        if inserted:
            logger.info(
                "WEBHOOK_MESSAGE_LOCK_ACQUIRED | provider_id=%s",
                provider_message_id,
            )
        else:
            logger.info(
                "WEBHOOK_DUPLICATE_MESSAGE_IGNORED | provider_id=%s",
                provider_message_id,
            )
        return inserted

    except Exception:
        db.rollback()
        logger.exception(
            "WEBHOOK_MESSAGE_LOCK_FAIL | provider_id=%s | fail_open",
            provider_message_id,
        )
        return True


# -------------------------------------------------
# Webhook
# -------------------------------------------------

@router.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    logger.info("WEBHOOK_ENTER")

    payload = await request.json()
    msg, sender, business_msisdn, provider_message_id = _extract_message(payload)

    if not msg or not sender or not business_msisdn:
        logger.warning(
            "WEBHOOK_INVALID_MESSAGE | sender=%s | business=%s",
            sender,
            business_msisdn,
        )
        return Response(status_code=200)

    # -------------------------------------------------
    # DB availability guard
    # -------------------------------------------------
    try:
        db.execute(text("SELECT 1"))
    except OperationalError:
        logger.critical("WEBHOOK_DB_UNAVAILABLE | degraded_mode")
        send_message(
            to_number=sender,
            text="⚠️ Service temporarily unavailable. Please try again shortly.",
        )
        return Response(status_code=200)

    # -------------------------------------------------
    # Duplicate protection
    # -------------------------------------------------
    if not _try_lock_provider_message(db, provider_message_id):
        logger.info("WEBHOOK_EXIT_DUPLICATE")
        return Response(status_code=200)

    # -------------------------------------------------
    # Background maintenance
    # -------------------------------------------------
    try:
        auto_close_expired_inspections(db)
    except Exception:
        logger.exception("WEBHOOK_BACKGROUND_TASK_FAIL | auto_close_inspections")

    # -------------------------------------------------
    # Dispatch (AUTHORITATIVE)
    # -------------------------------------------------
    logger.info(
        "WEBHOOK_DISPATCH_ENTER | sender=%s | business=%s | msg_type=%s",
        sender,
        business_msisdn,
        msg.get("type"),
    )

    handled = dispatch(
        db=db,
        msg=msg,
        sender=sender,
        business_msisdn=business_msisdn,
    )

    logger.info(
        "WEBHOOK_DISPATCH_EXIT | handled=%s | sender=%s | business=%s",
        handled,
        sender,
        business_msisdn,
    )

    # -------------------------------------------------
    # HARD STOP — NO FALLTHROUGH
    # -------------------------------------------------
    logger.info(
        "WEBHOOK_LIFECYCLE_END | sender=%s | business=%s",
        sender,
        business_msisdn,
    )
    return Response(status_code=200)
