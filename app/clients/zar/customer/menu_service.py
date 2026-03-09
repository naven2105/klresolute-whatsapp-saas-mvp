from __future__ import annotations

"""
File: menu_service.py
Path: app/clients/zar/customer/menu_service.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
ZAR customer food menu handler.

Rules:
- Customer-only logic for "food"
- Stores and reuses latest admin-sent food menu image
- Returns True if handled
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.messaging.client_messenger import send_message
from app.outbound.factory import get_meta_client

logger = logging.getLogger("zar.menu_service")


def handle_menu_command(
    *,
    db: Session,
    sender_msisdn: str,
    business_msisdn: str,
    message_text: str,
) -> bool:

    msg = (message_text or "").strip().lower()

    if msg != "food":
        return False

    try:
        row = db.execute(
            text(
                """
                SELECT media_id
                FROM r_zar__menu_images
                ORDER BY created_at DESC
                LIMIT 1
                """
            )
        ).fetchone()

        if not row:
            send_message(
                db=db,
                business_msisdn=business_msisdn,
                to_number=sender_msisdn,
                text="Food menu is currently unavailable.",
            )
            return True

        meta = get_meta_client(
            db=db,
            business_msisdn=business_msisdn,
        )

        meta.send_image_message(
            to_msisdn=sender_msisdn,
            media_id=row.media_id,
            caption=None,
        )

        return True

    except Exception:
        logger.exception(
            "ZAR_MENU_SEND_FAIL | to=%s",
            sender_msisdn,
        )
        send_message(
            db=db,
            business_msisdn=business_msisdn,
            to_number=sender_msisdn,
            text="Food menu is currently unavailable.",
        )
        return True


def store_menu_image(
    *,
    db: Session,
    sender_msisdn: str,
    business_msisdn: str,
    media_id: str | None,
) -> bool:

    if not media_id:
        send_message(
            db=db,
            business_msisdn=business_msisdn,
            to_number=sender_msisdn,
            text="Food menu image was not received.",
        )
        return True

    try:
        db.execute(
            text(
                """
                INSERT INTO r_zar__menu_images (media_id)
                VALUES (:media_id)
                """
            ),
            {"media_id": media_id},
        )
        db.commit()

        send_message(
            db=db,
            business_msisdn=business_msisdn,
            to_number=sender_msisdn,
            text="Food menu updated.",
        )
        return True

    except Exception:
        db.rollback()
        logger.exception(
            "ZAR_MENU_STORE_FAIL | sender=%s",
            sender_msisdn,
        )
        send_message(
            db=db,
            business_msisdn=business_msisdn,
            to_number=sender_msisdn,
            text="Food menu update failed.",
        )
        return True


def handle_drinks_command(
    *,
    db: Session,
    sender_msisdn: str,
    business_msisdn: str,
    message_text: str,
) -> bool:
    return False