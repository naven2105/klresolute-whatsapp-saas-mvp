from __future__ import annotations

"""
File: app/webhooks.py
Project: KLResolute WhatsApp SaaS MVP

PURPOSE:
Minimal WhatsApp webhook dispatcher.

LOCKED:
- Parse inbound payload safely
- Ignore non-message events (statuses, receipts, etc.)
- Dispatch ONLY real user messages
- Prevent duplicate processing using provider_message_id (NOT UUID)
"""

import logging
import re
from typing import Optional

from fastapi import APIRouter, Request, Response, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db import get_db
from app.inbound_dispatcher import dispatch
from app.clients.magen.auto_close import auto_close_expired_inspections

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
    """
    Returns (msg, sender_msisdn, business_msisdn, provider_message_id)
    or (None, None, None, None) if NOT a user message.
    """
    try:
        entry = payload["entry"][0]["changes"][0]["value"]

        # ---- GUARDRAIL: STATUS / DELIVERY CALLBACKS ----
        if "statuses" in entry:
            logger.warning(
                "WEBHOOK_STATUS_EVENT_IGNORED | keys=%s",
                list(entry.keys()),
            )
            return None, None, None, None

        messages = entry.get("messages")
        if not messages:
            logger.warning(
                "WEBHOOK_NON_MESSAGE_PAYLOAD | keys=%s",
                list(entry.keys()),
            )
            return None, None, None, None

        msg = messages[0]
        sender = msg.get("from")
        provider_message_id = msg.get("id")
        business_raw = entry.get("metadata", {}).get("display_phone_number")

        return (
            msg,
            _normalise_msisdn(sender),
            _normalise_msisdn(business_raw),
            provider_message_id,
        )

    except Exception as exc:
        logger.error(
            "PAYLOAD_PARSE_FAILED | error=%s | payload_keys=%s",
            exc,
            list(payload.keys()) if isinstance(payload, dict) else None,
            exc_info=True,
        )
        return None, None, None, None


def _is_duplicate_provider_message(db: Session, provider_message_id: str) -> bool:
    if not provider_message_id:
        logger.warning("DUPLICATE_CHECK_NO_PROVIDER_ID")
        return False

    try:
        row = db.execute(
            text(
                """
                SELECT 1
                FROM messages
                WHERE provider_message_id = :pid
                LIMIT 1
                """
            ),
            {"pid": provider_message_id},
        ).first()

        return bool(row)

    except Exception as exc:
        logger.error(
            "DUPLICATE_CHECK_FAILED | provider_id=%s | error=%s",
            provider_message_id,
            exc,
            exc_info=True,
        )
        return False  # fail-open


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
    except Exception as exc:
        logger.error("INVALID_JSON | error=%s", exc, exc_info=True)
        return Response(status_code=200)

    msg, sender, business_msisdn, provider_message_id = _extract_message(payload)

    # -------------------------------------------------
    # Ignore non-user messages
    # -------------------------------------------------
    if not msg:
        logger.info("WEBHOOK_IGNORED | reason=non_user_message")
        return Response(status_code=200)

    if not sender or not business_msisdn:
        logger.error(
            "INVALID_MESSAGE | sender=%s | business=%s | provider_id=%s",
            sender,
            business_msisdn,
            provider_message_id,
        )
        return Response(status_code=200)

    # -------------------------------------------------
    # Duplicate protection
    # -------------------------------------------------
    if _is_duplicate_provider_message(db, provider_message_id):
        logger.info(
            "DUPLICATE_MESSAGE_IGNORED | provider_id=%s | sender=%s",
            provider_message_id,
            sender,
        )
        return Response(status_code=200)

    # -------------------------------------------------
    # Background maintenance (safe)
    # -------------------------------------------------
    try:
        auto_close_expired_inspections(db)
    except Exception as exc:
        logger.error(
            "MAGEN_AUTO_CLOSE_FAILED | error=%s",
            exc,
            exc_info=True,
        )

    # -------------------------------------------------
    # Dispatch
    # -------------------------------------------------
    try:
        handled = dispatch(
            db=db,
            msg=msg,
            sender=sender,
            business_msisdn=business_msisdn,
        )

        logger.info(
            "DISPATCH_RESULT | handled=%s | sender=%s | business=%s",
            handled,
            sender,
            business_msisdn,
        )

    except Exception as exc:
        logger.error(
            "DISPATCH_FAILURE | sender=%s | business=%s | error=%s",
            sender,
            business_msisdn,
            exc,
            exc_info=True,
        )

    return Response(status_code=200)
