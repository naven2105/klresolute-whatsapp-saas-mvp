from __future__ import annotations

"""
File: app/webhooks.py
Project: KLResolute WhatsApp SaaS MVP

PURPOSE:
Minimal WhatsApp webhook dispatcher.

RESPONSIBILITIES (LOCKED):
- Parse inbound payload
- Extract sender + business MSISDN + message
- De-duplicate inbound messages (Meta retries)
- Dispatch to generic inbound dispatcher
- Stop at first module that claims the message

NO BUSINESS LOGIC HERE.
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
logging.basicConfig(level=logging.INFO)


# -------------------------------------------------
# Helpers (pure parsing only)
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

        if not msg:
            return None, None, None, None

        sender = msg.get("from")
        business_raw = entry.get("metadata", {}).get("display_phone_number")
        message_id = msg.get("id")

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

    if exists:
        return True

    db.execute(
        text(
            """
            INSERT INTO messages (message_id, created_at)
            VALUES (:message_id, now())
            """
        ),
        {"message_id": message_id},
    )
    db.commit()
    return False


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

    if not msg or not sender or not business_msisdn or not message_id:
        logger.warning(
            "INVALID_MESSAGE | sender=%s | business=%s",
            sender,
            business_msisdn,
        )
        return Response(status_code=200)

    # -------------------------------------------------
    # De-duplication (Meta retries)
    # -------------------------------------------------
    if _is_duplicate_message(db, message_id):
        logger.info(
            "DUPLICATE_MESSAGE_DROPPED | message_id=%s",
            message_id,
        )
        return Response(status_code=200)

    # -------------------------------------------------
    # SAFE BACKGROUND MAINTENANCE
    # -------------------------------------------------
    try:
        auto_close_expired_inspections(db)
    except Exception:
        logger.exception("MAGEN_AUTO_CLOSE_FAILED")

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

        if handled:
            logger.info(
                "MESSAGE_HANDLED | business=%s",
                business_msisdn,
            )
            return Response(status_code=200)

    except Exception:
        logger.exception(
            "DISPATCH_FAILURE | business=%s",
            business_msisdn,
        )

    return Response(status_code=200)
