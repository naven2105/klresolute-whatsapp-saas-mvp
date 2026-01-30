from __future__ import annotations

"""
File: app/webhooks.py
Project: KLResolute WhatsApp SaaS MVP

PURPOSE:
Minimal WhatsApp webhook dispatcher.

RESPONSIBILITIES (LOCKED):
- Parse inbound payload
- Extract sender + business MSISDN + message
- Prevent duplicate processing (string message_id)
- Dispatch to inbound dispatcher
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
    try:
        entry = payload["entry"][0]["changes"][0]["value"]
        msg = entry.get("messages", [None])[0]
        sender = msg.get("from") if msg else None
        business_raw = entry.get("metadata", {}).get("display_phone_number")
        message_id = msg.get("id") if msg else None

        return (
            msg,
            message_id,
            _normalise_msisdn(sender),
            _normalise_msisdn(business_raw),
        )

    except Exception:
        logger.exception("PAYLOAD_PARSE_FAILED")
        return None, None, None, None


def _is_duplicate_message(db: Session, message_id: str) -> bool:
    if not message_id:
        return False

    exists = db.execute(
        text(
            """
            SELECT 1
            FROM messages
            WHERE message_id = :message_id
            LIMIT 1
            """
        ),
        {"message_id": message_id},
    ).first()

    return exists is not None


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
        logger.warning("INVALID_JSON")
        return Response(status_code=200)

    msg, message_id, sender, business_msisdn = _extract_message(payload)

    if not msg or not sender or not business_msisdn:
        logger.warning(
            "INVALID_MESSAGE | sender=%s | business=%s",
            sender,
            business_msisdn,
        )
        return Response(status_code=200)

    # ----------------------------------
    # DUPLICATE PROTECTION (STRING SAFE)
    # ----------------------------------
    if _is_duplicate_message(db, message_id):
        logger.info("DUPLICATE_MESSAGE_IGNORED | message_id=%s", message_id)
        return Response(status_code=200)

    # ----------------------------------
    # SAFE BACKGROUND MAINTENANCE
    # ----------------------------------
    try:
        auto_close_expired_inspections(db)
    except Exception:
        logger.exception("MAGEN_AUTO_CLOSE_FAILED")

    # ----------------------------------
    # DISPATCH
    # ----------------------------------
    try:
        handled = dispatch(
            db=db,
            msg=msg,
            sender=sender,
            business_msisdn=business_msisdn,
        )

        if handled:
            logger.info("MESSAGE_HANDLED | business=%s", business_msisdn)
            return Response(status_code=200)

    except Exception:
        logger.exception("DISPATCH_FAILURE | business=%s", business_msisdn)
        return Response(status_code=200)

    logger.warning(
        "NO_HANDLER_MATCH | sender=%s | business=%s",
        sender,
        business_msisdn,
    )

    return Response(status_code=200)
