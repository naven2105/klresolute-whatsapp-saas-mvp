from __future__ import annotations

"""
File: admin_menu_service.py
Path: app/clients/fatginger/admin/admin_menu_service.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
FatGinger admin menu handler.

Rules:
- Admin only
- Returns True
"""

from sqlalchemy.orm import Session
from app.messaging.client_messenger import send_message


ADMIN_MENU_TEXT = (
    "🔧 FatGinger Admin Menu\n\n"
    "Available commands:\n\n"
    "survey: <question>\n"
    "Send a customer survey\n\n"
    "campaign: <message>\n"
    "Send marketing campaign\n\n"
    "announcement: <message>\n"
    "Send announcement\n\n"
    "Example:\n"
    "survey: How was your meal today?"
)


def handle_admin_menu(
    *,
    db: Session,
    sender_msisdn: str,
    business_msisdn: str,
) -> bool:

    send_message(
        db=db,
        business_msisdn=business_msisdn,
        to_number=sender_msisdn,
        text=ADMIN_MENU_TEXT,
    )

    return True