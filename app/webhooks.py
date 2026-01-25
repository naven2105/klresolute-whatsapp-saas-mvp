from __future__ import annotations

"""
File: app/webhooks.py
Project: KLResolute WhatsApp SaaS MVP

PURPOSE:
Minimal WhatsApp webhook dispatcher.

RESPONSIBILITIES (LOCKED):
- Parse inbound payload
- Extract sender + business MSISDN + message
- Dispatch to client handlers
- Stop at first handler that claims the message
- Send fallback clarification if no client matches

NO BUSINESS LOGIC HERE.
"""

import logging
import re
from typing import Optional

from fastapi import APIRouter, Request, Response, Depends
from sqlalchemy.orm import Session

from app.db import get_db

# ---- Client handlers (one per business) ----
from app.clients.pilateshq.inbound import handle_inbound as pilateshq_inbound
from app.clients.magen.inbound import handle_inbound as magen_inbound
from app.clients.galitos.inbound import handle_inbound as galitos_inbound

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
        sender = msg.get("from") if msg else None
        business_raw = entry.get("metadata", {}).get("display_phone_number")
        return msg, _normalise_msisdn(sender), _normalise_msisdn(business_raw)
    except Exception:
        logger.exception("PAYLOAD_PARSE_FAILED")
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
        logger.warning("INVALID_JSON")
        return Response(status_code=200)

    msg, sender, business_msisdn = _extract_message(payload)

    if not msg or not sender or not business_msisdn:
        logger.warning(
            "INVALID_MESSAGE | sender=%s | business=%s",
            sender,
            business_msisdn,
        )
        return Response(status_code=200)

    # ---- Ordered client dispatch ----
    handlers = [
        pilateshq_inbound,
        magen_inbound,
        galitos_inbound,
    ]

    for handler in handlers:
        try:
            if handler(
                db=db,
                msg=msg,
                sender=sender,
                business_msisdn=business_msisdn,
            ):
                logger.info(
                    "MESSAGE_HANDLED | handler=%s | business=%s",
                    handler.__module__,
                    business_msisdn,
                )
                return Response(status_code=200)
        except Exception:
            logger.exception(
                "HANDLER_FAILURE | handler=%s | business=%s",
                handler.__module__,
                business_msisdn,
            )
            return Response(status_code=200)

    # ---- Fallback: unknown / unconfigured number ----
    logger.warning(
        "NO_HANDLER_MATCH | sender=%s | business=%s",
        sender,
        business_msisdn,
    )

    return Response(status_code=200)
