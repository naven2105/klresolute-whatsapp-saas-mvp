"""
File: app/webhooks.py
Path: app/webhooks.py

Project: KLResolute WhatsApp SaaS MVP

Purpose:
Inbound WhatsApp webhook entrypoint.
- Parse payload
- Route to correct handler (media → admin → client)
"""

import logging
import os
import re

from fastapi import APIRouter, Request, Response, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.outbound.factory import get_meta_client

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
    try:
        payload = await request.json()
    except Exception:
        return Response(status_code=200)

    msg, sender_raw = _extract_message(payload)
    sender = _normalise_msisdn(sender_raw)

    if not msg or not sender:
        return Response(status_code=200)

    # ==================================================
    # 1. MEDIA HANDLER (admin image intake)
    # ==================================================
    if handle_media_message(
        db=db,
        sender_number=sender,
        msg=msg,
        admin_allowlist=ADMIN_ALLOWLIST,
    ):
        return Response(status_code=200)

    # ==================================================
    # 2. ADMIN COMMANDS (Tier-1)
    # ==================================================
    if msg.get("type") == "text":
        text = msg["text"]["body"].strip()

        if handle_admin_command(
            db=db,
            sender_number=sender,
            message_text=text,
            admin_allowlist=ADMIN_ALLOWLIST,
        ):
            return Response(status_code=200)

    # ==================================================
    # 3. CLIENT SELF-SERVICE (STOP / RESUME)
    # ==================================================
    if handle_client_command(
        db=db,
        sender_number=sender,
        msg=msg,
        admin_allowlist=ADMIN_ALLOWLIST,
    ):
        return Response(status_code=200)

    # ==================================================
    # Ignore everything else (MVP)
    # ==================================================
    return Response(status_code=200)
