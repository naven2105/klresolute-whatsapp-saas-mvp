from __future__ import annotations

"""
File: app/modules/broadcast/handler.py
Path: app/modules/broadcast/handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Inbound entry point for Broadcast module.

Responsibilities (LOCKED):
- Admin: handle BROADCAST text + image (specials)
- Customer: handle SPECIAL / SPECIALS request
- Delegate all persistence + delivery to service layer
- Return True if message was handled

NO direct DB schema logic.
NO Meta client creation here.
"""

import logging
from sqlalchemy.orm import Session

from app.modules.broadcast.service import (
    handle_text_broadcast,
    handle_image_broadcast,
    send_latest_special_to_customer,
)
from app.services.client_commands import is_admin_message

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

    msg_type = msg.get("type")

    # =================================================
    # CUSTOMER: request latest special
    # =================================================
    if msg_type == "text":
        body = msg.get("text", {}).get("body", "").strip()
        if not body:
            return False

        upper = body.upper()

        if upper in ("SPECIAL", "SPECIALS"):
            send_latest_special_to_customer(
                db=db,
                business_msisdn=business_msisdn,
                customer_msisdn=sender,
            )
            logger.info(
                "SPECIAL_SENT_TO_CUSTOMER | business=%s | customer=%s",
                business_msisdn,
                sender,
            )
            return True

    # =================================================
    # ADMIN ONLY from here
    # =================================================
    if not is_admin_message(sender, admin_allowlist):
        return False

    # ----------------------------------
    # ADMIN: TEXT broadcast
    # ----------------------------------
    if msg_type == "text":
        body = msg.get("text", {}).get("body", "").strip()
        if not body:
            return False

        upper = body.upper()

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
    # ADMIN: IMAGE broadcast (specials)
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
