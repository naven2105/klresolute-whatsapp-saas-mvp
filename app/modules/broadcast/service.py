from __future__ import annotations

"""
File: app/modules/broadcast/service.py
Path: app/modules/broadcast/service.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Broadcast service layer.

Responsibilities (LOCKED):
- Persist broadcast intent
- Resolve recipients
- Delegate outbound delivery
- NO inbound parsing
- NO permission checks
"""

import logging
from sqlalchemy.orm import Session

from app.modules.broadcast.repo import (
    save_text_broadcast,
    save_image_broadcast,
    get_broadcast_recipients,
)
from app.outbound.factory import get_meta_client

logger = logging.getLogger("module.broadcast.service")


# -------------------------------------------------
# TEXT broadcast
# -------------------------------------------------

def handle_text_broadcast(
    *,
    db: Session,
    business_msisdn: str,
    sender: str,
    text: str,
) -> None:
    """
    Persist and deliver a text broadcast.
    """

    broadcast_id = save_text_broadcast(
        db=db,
        business_msisdn=business_msisdn,
        sender=sender,
        text=text,
    )

    recipients = get_broadcast_recipients(db, business_msisdn)
    meta = get_meta_client()

    logger.info(
        "BROADCAST_TEXT_SEND_BEGIN | id=%s | recipients=%s",
        broadcast_id,
        len(recipients),
    )

    for msisdn in recipients:
        try:
            meta.send_session_message(
                to_msisdn=msisdn,
                text=text,
            )
        except Exception:
            logger.exception(
                "BROADCAST_TEXT_SEND_FAIL | id=%s | to=%s",
                broadcast_id,
                msisdn,
            )


# -------------------------------------------------
# IMAGE broadcast (specials)
# -------------------------------------------------

def handle_image_broadcast(
    *,
    db: Session,
    business_msisdn: str,
    sender: str,
    media_id: str,
    caption: str | None,
) -> None:
    """
    Persist and deliver an image broadcast.
    """

    broadcast_id = save_image_broadcast(
        db=db,
        business_msisdn=business_msisdn,
        sender=sender,
        media_id=media_id,
        caption=caption,
    )

    recipients = get_broadcast_recipients(db, business_msisdn)
    meta = get_meta_client()

    logger.info(
        "BROADCAST_IMAGE_SEND_BEGIN | id=%s | recipients=%s",
        broadcast_id,
        len(recipients),
    )

    for msisdn in recipients:
        try:
            meta.send_image_message(
                to_msisdn=msisdn,
                media_id=media_id,
                caption=caption,
            )
        except Exception:
            logger.exception(
                "BROADCAST_IMAGE_SEND_FAIL | id=%s | to=%s",
                broadcast_id,
                msisdn,
            )
