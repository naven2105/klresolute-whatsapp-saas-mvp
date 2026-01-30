from __future__ import annotations

"""
File: app/webhooks.py
Project: KLResolute WhatsApp SaaS MVP

PURPOSE:
Minimal WhatsApp webhook dispatcher.

LOCKED RESPONSIBILITIES:
- Accept ONLY real inbound user messages
- Ignore status / delivery / read callbacks
- Never dispatch malformed payloads
- Never reply to Meta status events
"""

import logging
import re
from typing import Optional

from fastapi import APIRouter, Request, Response, Depends
from sqlalchemy.orm import Session

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
    Returns (msg, sender, business_msisdn)
    OR (None, None, None) if NOT a user message.
    """

    try:
        entry = payload["entry"][0]["changes"][0]["value"]

        # ---- HARD STOP: status callbacks ----
        if "messages" not in entry:
            logger.warning(
                "WEBHOOK_NON_MESSAGE_PAYLOAD | keys=%s",
                list(entry.keys()),
            )
            return None, None, None

        msg = entry["messages"][0]

        sender = _normalise_msisdn(msg.get("from"))
        business = _normalise_msisdn(
            entry.get("metadata", {}).get("display_phone_number")
        )

        if not sender or not business:
            logger.error(
                "WEBHOOK_BAD_MESSAGE | sender=%s | business=%s | msg=%s",
                sender,
                business,
                msg,
            )
            return None, None, None

        return msg, sender, business

    except Exception as exc:
        logger.exception("WEBHOOK_PARSE_FAILED | error=%s", exc)
        return None, None, None


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
        logger.error("WEBHOOK_INVALID_JSON")
        return Response(status_code=200)

    msg, sender, business_msisdn = _extract_message(payload)

    # ---- FINAL HARD STOP ----
    if msg is None:
        return Response(status_code=200)

    # ---- SAFE background maintenance ----
    try:
        auto_close_expired_inspections(db)
    except Exception:
        logger.exception("MAGEN_AUTO_CLOSE_FAILED")

    # ---- Dispatch ----
    try:
        handled = dispatch(
            db=db,
            msg=msg,
            sender=sender,
            business_msisdn=business_msisdn,
        )

        if handled:
            logger.info(
                "MESSAGE_HANDLED | sender=%s | business=%s",
                sender,
                business_msisdn,
            )

    except Exception:
        logger.exception(
            "DISPATCH_FAILURE | sender=%s | business=%s",
            sender,
            business_msisdn,
        )

    return Response(status_code=200)
