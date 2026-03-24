# ==================================================
# File: main_menu_service.py
# Path: app/clients/klr_demo/customer/main_menu_service.py
# Project: KLResolute WhatsApp SaaS MVP
#
# Patch:
# - Add logo support via campaigns table (type='logo')
# ==================================================

from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy import text
from app.messaging.client_messenger import send_message


MAIN_MENU_TEXT = (
    "KLResolute Demo\n\n"
    "How can we help you today?\n\n"
    "* menu — View offerings\n"
    "* options — Show menu\n"
    "* specials — Latest updates\n"
    "* book — Make a booking\n"
    "* about — Learn more\n\n"
    "Or just ask us anything 😊"
)


def handle_main_menu(
    *,
    db: Session,
    sender_msisdn: str,
    business_msisdn: str,
    message_text: str,
) -> bool:

    # 🔹 FETCH LOGO (NEW)
    result = db.execute(
        text(
            """
            SELECT image_url
            FROM r_klr_demo__campaigns
            WHERE type = 'logo'
            ORDER BY sent_at DESC
            LIMIT 1
            """
        )
    ).fetchone()

    # 🔹 SEND LOGO IF EXISTS
    if result and result.image_url:
        send_message(
            db=db,
            business_msisdn=business_msisdn,
            to_number=sender_msisdn,
            image_id=result.image_url,  # matches your campaign logic
        )

    # 🔹 EXISTING MENU TEXT
    send_message(
        db=db,
        business_msisdn=business_msisdn,
        to_number=sender_msisdn,
        text=MAIN_MENU_TEXT,
    )

    return True