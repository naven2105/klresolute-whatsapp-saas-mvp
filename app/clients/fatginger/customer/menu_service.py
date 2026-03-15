# ==================================================
# File: menu_service.py
# Path: app/clients/fatginger/customer/menu_service.py
# Project: KLResolute WhatsApp SaaS MVP
#
# Update:
# - Standardised to ZAR menu image architecture
# - Uses r_fg__menu_images
# ==================================================

from __future__ import annotations

import logging
import time
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.messaging.client_messenger import send_message

logger = logging.getLogger("fatginger.menu_service")


# --------------------------------------------------
# TEMP STORAGE WITH EXPIRY
# --------------------------------------------------

pending_menu_updates: dict[str, dict] = {}

MENU_UPDATE_EXPIRY_SECONDS = 60


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

    pending_menu_updates[sender_msisdn] = {
        "media_id": media_id,
        "timestamp": time.time(),
    }

    logger.info(
        "FG_MENU_UPDATE_PENDING | sender=%s | media_id=%s",
        sender_msisdn,
        media_id,
    )

    send_message(
        db=db,
        business_msisdn=business_msisdn,
        to_number=sender_msisdn,
        text=(
            "You are about to update the current food menu image.\n\n"
            "Reply YES to save this image as the food menu.\n"
            "Reply NO to cancel.\n\n"
            "This request expires in 1 minute."
        ),
    )

    return True


# --------------------------------------------------
# ADMIN CONFIRMATION
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

    entry = pending_menu_updates[sender_msisdn]

    if time.time() - entry["timestamp"] > MENU_UPDATE_EXPIRY_SECONDS:

        pending_menu_updates.pop(sender_msisdn, None)

        send_message(
            db=db,
            business_msisdn=business_msisdn,
            to_number=sender_msisdn,
            text="Food menu update expired. Please send the image again.",
        )

        return True

    msg = message_text.strip().lower()

    if msg == "no":

        pending_menu_updates.pop(sender_msisdn, None)

        send_message(
            db=db,
            business_msisdn=business_msisdn,
            to_number=sender_msisdn,
            text="Food menu update cancelled.",
        )

        return True

    if msg == "yes":

        media_id = entry["media_id"]

        pending_menu_updates.pop(sender_msisdn, None)

        db.execute(
            text(
                """
                INSERT INTO r_fg__menu_images (media_id, created_at)
                VALUES (:media_id, NOW())
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

        logger.info(
            "FG_MENU_UPDATED | sender=%s | media_id=%s",
            sender_msisdn,
            media_id,
        )

        return True

    return False


# --------------------------------------------------
# CUSTOMER FOOD COMMAND
# --------------------------------------------------

def handle_menu_command(
    *,
    db: Session,
    sender_msisdn: str,
    business_msisdn: str,
    message_text: str,
) -> bool:

    if message_text.lower() != "food":
        return False

    result = db.execute(
        text(
            """
            SELECT media_id
            FROM r_fg__menu_images
            ORDER BY created_at DESC
            LIMIT 1
            """
        )
    ).fetchone()

    if not result:

        send_message(
            db=db,
            business_msisdn=business_msisdn,
            to_number=sender_msisdn,
            text="Food menu not available yet.",
        )

        return True

    send_message(
        db=db,
        business_msisdn=business_msisdn,
        to_number=sender_msisdn,
        image_id=result.media_id,
    )

    return True