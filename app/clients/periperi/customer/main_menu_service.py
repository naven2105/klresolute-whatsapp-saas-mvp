from __future__ import annotations

"""
File: main_menu_service.py
Path: app/clients/periperi/customer/main_menu_service.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
periperi chatbot main menu handler (tenant-local).

Rules:
- Handles "menu"
- Handles unknown commands (fallback)
- Customer-only logic
- No dispatcher logic
"""

from sqlalchemy.orm import Session
from app.messaging.client_messenger import send_message


MAIN_MENU_TEXT = (
    "🐔 O' Peri Peri Edenvale\n\n"
    "How can we help you today?\n\n"
    "* food — View our menu\n"
    "* specials — See current specials\n"
    "* book — Reserve a table\n"
    "* about — Learn more about us\n"
    "* feedback: — Message management\n\n"
    "Or just ask us anything 😊"
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