# ==================================================
# File: menu_update_handler.py
# Path: app/clients/zar/handlers/menu_update_handler.py
# Project: KLResolute WhatsApp SaaS MVP
#
# Purpose:
# Admin flow to update ZAR food menu image.
#
# Behaviour:
# - Admin sends image with caption "food" or "food menu"
# - Bot asks confirmation
# - YES → save image to r_zar__menu_images
# - NO  → cancel
#
# Isolation:
# - ZAR tenant only
# - No campaign handler interaction
# ==================================================

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.messaging.client_messenger import send_message

logger = logging.getLogger("zar.menu_update")

pending_menu_updates: dict[str, dict] = {}

EXPIRY_SECONDS = 60


def handle_menu_update_image(
    *,
    db: Session,
    sender_msisdn: str,
    business_msisdn: str,
    media_id: str | None,
    caption: str | None,
) -> bool:

    caption = (caption or "").strip().lower()

    if caption not in {"food", "food menu"}:
        return False

    if not media_id:
        return True

    pending_menu_updates[sender_msisdn] = {
        "media_id": media_id,
        "created_at": datetime.utcnow(),
    }

    send_message(
        db=db,
        business_msisdn=business_msisdn,
        to_number=sender_msisdn,
        text=(
            "You are about to update the current food menu image.\n\n"
            "Reply YES to save this image as the food menu.\n"
            "Reply NO to cancel.\n"
            "This request expires in 1 minute."
        ),
    )

    return True


def handle_menu_update_confirmation(
    *,
    db: Session,
    sender_msisdn: str,
    business_msisdn: str,
    message_text: str,
) -> bool:

    msg = (message_text or "").strip().lower()

    pending = pending_menu_updates.get(sender_msisdn)

    if not pending:
        return False

    if datetime.utcnow() - pending["created_at"] > timedelta(seconds=EXPIRY_SECONDS):

        del pending_menu_updates[sender_msisdn]

        send_message(
            db=db,
            business_msisdn=business_msisdn,
            to_number=sender_msisdn,
            text="Food menu update expired.",
        )

        return True

    if msg == "yes":

        try:

            db.execute(
                text(
                    """
                    INSERT INTO r_zar__menu_images (media_id)
                    VALUES (:media_id)
                    """
                ),
                {"media_id": pending["media_id"]},
            )

            db.commit()

        except Exception:

            db.rollback()

            logger.exception("ZAR_MENU_SAVE_FAIL")

        del pending_menu_updates[sender_msisdn]

        send_message(
            db=db,
            business_msisdn=business_msisdn,
            to_number=sender_msisdn,
            text="Food menu updated.",
        )

        return True

    if msg == "no":

        del pending_menu_updates[sender_msisdn]

        send_message(
            db=db,
            business_msisdn=business_msisdn,
            to_number=sender_msisdn,
            text="Food menu update cancelled.",
        )

        return True

    send_message(
        db=db,
        business_msisdn=business_msisdn,
        to_number=sender_msisdn,
        text="Please reply YES to save or NO to cancel.",
    )

    return True