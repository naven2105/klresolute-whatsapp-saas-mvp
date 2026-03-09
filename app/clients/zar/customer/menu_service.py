# ==================================================
# File: menu_service.py
# Path: app/clients/zar/customer/menu_service.py
# Project: KLResolute WhatsApp SaaS MVP
# ==================================================

from __future__ import annotations

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger("zar.menu_service")


# --------------------------------------------------
# TEMP STORAGE FOR CONFIRMATION
# --------------------------------------------------

pending_menu_updates: dict[str, str] = {}


# --------------------------------------------------
# ADMIN IMAGE UPDATE
# --------------------------------------------------

def store_menu_image(
    *,
    db: Session,
    sender_msisdn: str,
    business_msisdn: str,
    media_id: str,
) -> bool:

    pending_menu_updates[sender_msisdn] = media_id

    logger.info(
        "ZAR_MENU_UPDATE_PENDING | sender=%s | media_id=%s",
        sender_msisdn,
        media_id,
    )

    return True


# --------------------------------------------------
# ADMIN CONFIRMATION HANDLER
# --------------------------------------------------

def handle_menu_confirmation(
    *,
    db: Session,
    sender_msisdn: str,
    business_msisdn: str,
    message_text: str,
) -> bool:

    if sender_msisdn not in pending_menu_updates:
        return False

    response = message_text.strip().lower()

    if response == "no":

        pending_menu_updates.pop(sender_msisdn, None)

        logger.info(
            "ZAR_MENU_UPDATE_CANCELLED | sender=%s",
            sender_msisdn,
        )

        return True

    if response == "yes":

        media_id = pending_menu_updates.pop(sender_msisdn)

        db.execute(
            text(
                """
                INSERT INTO r_zar__menu_images
                (media_id, created_at)
                VALUES (:media_id, NOW())
                """
            ),
            {"media_id": media_id},
        )

        db.commit()

        logger.info(
            "ZAR_MENU_UPDATED | sender=%s | media_id=%s",
            sender_msisdn,
            media_id,
        )

        return True

    return False


# --------------------------------------------------
# CUSTOMER COMMAND
# --------------------------------------------------

def handle_menu_command(
    *,
    db: Session,
    sender_msisdn: str,
    business_msisdn: str,
) -> bool:

    result = db.execute(
        text(
            """
            SELECT media_id
            FROM r_zar__menu_images
            ORDER BY created_at DESC
            LIMIT 1
            """
        )
    ).fetchone()

    if not result:

        logger.info(
            "ZAR_MENU_NOT_FOUND | sender=%s",
            sender_msisdn,
        )

        return True

    media_id = result[0]

    logger.info(
        "ZAR_MENU_SENT | sender=%s | media_id=%s",
        sender_msisdn,
        media_id,
    )

    return True