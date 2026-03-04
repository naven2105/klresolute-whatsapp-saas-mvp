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
    "* survey: <question> – Send customer survey\n\n"
    "Example:\n"
    "survey: How was your meal today?\n\n"

    "────────────────\n\n"

    "🎯 Announcement\n\n"
    "* announcement: <text> – Send text announcement\n"
    "* Send image with optional caption – Send image announcement\n\n"

    "Notes:\n"
    "• Only one active announcement\n"
    "• New announcement replaces the previous one\n"
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