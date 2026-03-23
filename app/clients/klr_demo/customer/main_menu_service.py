from __future__ import annotations

"""
File: main_menu_service.py
Path: app/clients/klr_demo/customer/main_menu_service.py
Project: KLResolute WhatsApp SaaS MVP
"""

from sqlalchemy.orm import Session
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

    # 🔹 Send logo (URL)
    send_message(
        db=db,
        business_msisdn=business_msisdn,
        to_number=sender_msisdn,
        image_url="https://klresolute.co.za/logos/demo_logo.png",
    )

    # 🔹 Menu text
    send_message(
        db=db,
        business_msisdn=business_msisdn,
        to_number=sender_msisdn,
        text=MAIN_MENU_TEXT,
    )

    return True