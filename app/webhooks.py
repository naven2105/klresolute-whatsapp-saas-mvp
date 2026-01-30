from __future__ import annotations

"""
File: app/webhooks.py
Project: KLResolute WhatsApp SaaS MVP

PURPOSE:
Minimal WhatsApp webhook dispatcher.

RESPONSIBILITIES (LOCKED):
- Parse inbound payload
- Extract sender + business MSISDN + message
- Dispatch to generic inbound dispatcher
- Stop at first module that claims the message
- Log and ignore non-message payloads (statuses, receipts, etc.)

NO BUSINESS LOGIC HERE.
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
    """
    Extract ONLY real inbound user messages.
    Logs full payload if structure is unexpected.
    """
    try:
        entry = payload["entry"][0]["changes"][0]["value"]

        # ---- HARD FILTER: ignore statuses / receipts ----
        if "messages" not in entry:
            logger.warning(
                "WEBHOOK_NON_MESSAGE_PAYLOAD | keys=%s | payload=%s",
                list(entry.keys()),
                payload,
            )
            return None, None, None

        msg = entry["messages"][0]
        sender = msg.get("from")

        business_raw = entry.get("metadata", {}).get("display_phone_number")

        return (
            msg,
            _normalise_msisdn(sender),
            _normalise_msisdn(business_raw),
        )

    except Exception:
        logger.exception(
            "PAYLOAD_PARSE_FATAL | payload=%s",
            payload,
        )
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

    # -------------------------------------------------
    # LOG WHY WE DROPPED IT
    # -------------------------------------------------
    if not msg or not sender or not business_msisdn:
        logger.error(
            "WEBHOOK_DROP | reason=missing_fields | sender=%s | business=%s | payload=%s",
            sender,
            business_msisdn,
            payload,
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
                "MESSAGE_HANDLED | sender=%s | business=%s",
                sender,
                business_msisdn,
            )
            return Response(status_code=200)

    except Exception:
        logger.exception(
            "DISPATCH_FAILURE | sender=%s | business=%s",
            sender,
            business_msisdn,
        )
        return Response(status_code=200)

    logger.warning(
        "NO_HANDLER_MATCH | sender=%s | business=%s",
        sender,
        business_msisdn,
    )

    return Response(status_code=200)
