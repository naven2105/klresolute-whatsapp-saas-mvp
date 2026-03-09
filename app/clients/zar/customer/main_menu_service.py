from __future__ import annotations

"""
File: main_menu_service.py
Path: app/clients/zar/customer/main_menu_service.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
ZAR chatbot main menu handler (tenant-local).

Rules:
- Handles "menu"
- Handles unknown commands (fallback)
- Customer-only logic
- No dispatcher logic
"""

from sqlalchemy.orm import Session
from app.messaging.client_messenger import send_message


MAIN_MENU_TEXT = (
    "☕ Welcome to The ZAR Café\n\n"
    "Success starts with a good foundation.\n"
    "Fuel your day at Tree Tops Houghton.\n\n"
    "Please choose an option:\n\n"
    "* food — View today's menu\n"
    "* specials — View current specials\n"
    "* book — Reserve a table\n"
    "* feedback: — Send a message to management\n"
    "* about — Learn more about us\n\n"
    "To book, please use this format:\n"
    "book 4 DD/MM HH:MM\n\n"
    "To send feedback:\n"
    "feedback: Your message to admin\n\n"
    "Reply STOP anytime to unsubscribe."
)


def handle_main_menu(
    *,
    db: Session,
    sender_msisdn: str,
    business_msisdn: str,
    message_text: str,
) -> bool:
    """
    Always returns True (fallback handler).
    """

    send_message(
        db=db,
        business_msisdn=business_msisdn,
        to_number=sender_msisdn,
        text=MAIN_MENU_TEXT,
    )

    return True