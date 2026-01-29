from __future__ import annotations

"""
File: app/modules/broadcast/handler.py
Path: app/modules/broadcast/handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Inbound entry point for Broadcast module.

Responsibilities (LOCKED):
- Decide if inbound message is a broadcast command
- Validate admin permission
- Persist broadcast intent
- Delegate delivery to service layer
- Return True if message was handled

NO direct DB schema logic.
NO Meta client creation here.
"""

import logging
from sqlalchemy.orm import Session

from app.modules.broadcast.service import (
    handle_text_broadcast,
    handle_image_broadcast,
)

# ✅ DO NOT import app.handlers.client_commands (too many legacy dependencies)
from app.utils.admin import is_admin_message

logger = logging.getLogger("module.broadcast")


def handle(
    *,
    db: Session,
    msg: dict,
    sender: str,
    business_msisdn: str,
    admin_allowlist: set[str],
) -> bool:
    """
    Entry point for Broadcast module.
    """

    # ----------------------------------
    # Admin check
    # ----------------------------------
    if not is_admin_message(sender, admin_allowlist):
        return False

    msg_type = msg.get("type")

    # ----------------------------------
    # TEXT broadcast
    # ----------------------------------
    if msg_type == "text":
        body = msg.get("text", {}).get("body", "").strip()
        if not body:
            return False

        upper = body.upper()

        # Explicit BROADCAST command only
        if not upper.startswith("BROADCAST:"):
            return False

        text = body[len("BROADCAST:") :].strip()
        if not text:
            return True  # swallow silently

        handle_text_broadcast(
            db=db,
            business_msisdn=business_msisdn,
            sender=sender,
            text=text,
        )

        logger.info(
            "BROADCAST_TEXT_HANDLED | business=%s | sender=%s",
            business_msisdn,
            sender,
        )
        return True

    # ----------------------------------
    # IMAGE broadcast (specials)
    # ----------------------------------
    if msg_type == "image":
        image = msg.get("image", {})
        media_id = image.get("id")
        caption = image.get("caption")

        if not media_id:
            return False

        handle_image_broadcast(
            db=db,
            business_msisdn=business_msisdn,
            sender=sender,
            media_id=media_id,
            caption=caption,
        )

        logger.info(
            "BROADCAST_IMAGE_HANDLED | business=%s | sender=%s",
            business_msisdn,
            sender,
        )
        return True

    return False
