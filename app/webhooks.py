"""
File: app/webhooks.py
Path: app/webhooks.py

Project: KLResolute WhatsApp SaaS MVP

Purpose:
Inbound WhatsApp webhook entrypoint.
- Parse payload
- Route to correct handler (media → admin → client)
- Log full processing flow for debugging
"""

import logging
import os
import re

from fastapi import APIRouter, Request, Response, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.handlers.admin_commands import handle_admin_command
from app.handlers.client_commands import handle_client_command
from app.handlers.media_handler import handle_media_message

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

logger = logging.getLogger("webhooks")
logging.basicConfig(level=logging.INFO)

# Admin allowlist (comma-separated MSISDNs)
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
        sender = msg.get("from")
        return msg, sender
    except Exception:
        return None, None


@router.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    logger.info("▶️ WhatsApp webhook hit")

    try:
        payload = await request.json()
        logger.info("📦 Payload JSON parsed")
    except Exception:
        logger.info("❌ Failed to parse JSON payload")
        return Response(status_code=200)

    msg, sender_raw = _extract_message(payload)
    logger.info(f"✉️ Message extracted: {bool(msg)} | sender_raw={sender_raw}")

    sender = _normalise_msisdn(sender_raw)
    logger.info(f"📞 Normalised sender: {sender}")

    if not msg or not sender:
        logger.info("⛔ No valid message or sender — exiting")
        return Response(status_code=200)

    # ==================================================
    # 1. MEDIA HANDLER
    # ==================================================
    media_handled = handle_media_message(
        db=db,
        sender=sender,
        msg=msg,
        admin_allowlist=ADMIN_ALLOWLIST,
    )
    logger.info(f"🖼️ Media handler handled={media_handled}")

    if media_handled:
        return Response(status_code=200)

    # ==================================================
    # TEXT MESSAGE ROUTING
    # ==================================================
    if msg.get("type") == "text":
        text = msg["text"]["body"]
        logger.info(f"💬 Text message body='{text}'")

        admin_handled = handle_admin_command(
            db=db,
            sender_number=sender,
            message_text=text,
            admin_allowlist=ADMIN_ALLOWLIST,
        )
        logger.info(f"🛠️ Admin handler handled={admin_handled}")

        client_handled = handle_client_command(
            db=db,
            sender_number=sender,
            message_text=text,
        )
        logger.info(f"👤 Client handler handled={client_handled}")

    logger.info("✅ Webhook processing complete")
    return Response(status_code=200)
