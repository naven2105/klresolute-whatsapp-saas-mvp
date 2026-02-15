from __future__ import annotations

"""
File: app/modules/broadcast/service.py
Path: app/modules/broadcast/service.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Broadcast service layer.

STATUS:
⚠️ ARCHIVED / LEGACY

Migration Update:
- Enforced business-scoped Meta client
- No global env sender usage
- Defensive rollback protection
- No behavioural changes
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
# TEXT broadcast (ARCHIVED)
# -------------------------------------------------

def handle_text_broadcast(
    *,
    db: Session,
    business_msisdn: str,
    sender: str,
    text: str,
) -> None:
    try:
        db.rollback()
    except Exception:
        pass

    broadcast_id = save_text_broadcast(
        db=db,
        business_msisdn=business_msisdn,
        sender=sender,
        text=text,
    )

    recipients = get_broadcast_recipients(db, business_msisdn)

    meta = get_meta_client(
        db=db,
        business_msisdn=business_msisdn,
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
# IMAGE broadcast (ARCHIVED)
# -------------------------------------------------

def handle_image_broadcast(
    *,
    db: Session,
    business_msisdn: str,
    sender: str,
    media_id: str,
    caption: str | None,
) -> None:
    try:
        db.rollback()
    except Exception:
        pass

    broadcast_id = save_image_broadcast(
        db=db,
        business_msisdn=business_msisdn,
        sender=sender,
        media_id=media_id,
        caption=caption,
    )

    recipients = get_broadcast_recipients(db, business_msisdn)

    meta = get_meta_client(
        db=db,
        business_msisdn=business_msisdn,
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


# -------------------------------------------------
# CUSTOMER: request latest special (ARCHIVED)
# -------------------------------------------------

def send_latest_special_to_customer(
    *,
    db: Session,
    business_msisdn: str,
    to_msisdn: str,
) -> bool:
    """
    LEGACY / ARCHIVED

    Retained for backward compatibility.
    """
    return False
