# ==================================================
# File: admin_menu_service.py
# Path: app/clients/fatginger/admin/admin_menu_service.py
# Project: KLResolute WhatsApp SaaS MVP
#
# Purpose:
# FatGinger Admin Menu
#
# Rules:
# - Admin only
# - Text only
# - No dispatcher logic
# ==================================================

from __future__ import annotations

from sqlalchemy.orm import Session
from app.messaging.client_messenger import send_message


ADMIN_MENU_TEXT = (
    "🛠️ Admin Menu\n\n"
    "📊 Surveys\n\n"
    "Start a survey:\n\n"
    "SURVEY: <question>\n\n"
    "Example:\n"
    "SURVEY: How was your meal today?\n\n"
    "Customers receive the survey and can respond.\n\n"
    "────────────────\n\n"
    "🎯 Announcement\n\n"
    "Text announcement:\n"
    "ANNOUNCEMENT: <message>\n\n"
    "Image announcement:\n"
    "Send an image with optional caption\n\n"
    "A preview will be shown.\n"
    "Reply YES to confirm sending.\n\n"
    "Notes:\n"
    "• Only one active announcement\n"
    "• New announcement replaces previous one\n"
    "• Customers type: announcements"
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