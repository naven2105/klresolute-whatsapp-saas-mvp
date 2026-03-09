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

    from app.meta.send import send_text_message

    pending_menu_updates[sender_msisdn] = media_id

    send_text_message(
        to=sender_msisdn,
        business_msisdn=business_msisdn,
        text=(
            "You are about to update the current food menu image.\n\n"
            "Reply YES to save this image as the food menu.\n"
            "Reply NO to cancel."
        ),
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

    from app.meta.send import send_text_message

    if sender_msisdn not in pending_menu_updates:
        return False

    response = message_text.strip().lower()

    if response == "no":

        pending_menu_updates.pop(sender_msisdn, None)

        send_text_message(
            to=sender_msisdn,
            business_msisdn=business_msisdn,
            text="Food menu update cancelled.",
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

        send_text_message(
            to=sender_msisdn,
            business_msisdn=business_msisdn,
            text="Food menu updated.",
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

    from app.meta.send import send_image_message, send_text_message

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

        send_text_message(
            to=sender_msisdn,
            business_msisdn=business_msisdn,
            text="Food menu is not available yet.",
        )

        return True

    media_id = result[0]

    send_image_message(
        to=sender_msisdn,
        business_msisdn=business_msisdn,
        media_id=media_id,
    )

    return True