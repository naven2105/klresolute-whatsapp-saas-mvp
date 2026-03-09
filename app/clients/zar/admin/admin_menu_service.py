from __future__ import annotations

# ==================================================
# File: admin_menu_service.py
# Path: app/clients/zar/admin/admin_menu_service.py
# Project: KLResolute WhatsApp SaaS MVP
#
# Purpose:
# ZAR Admin Menu
#
# Rules:
# - Admin only
# - Text only
# - No dispatcher logic
# ==================================================

from sqlalchemy.orm import Session
from app.messaging.client_messenger import send_message


ADMIN_MENU_TEXT = (
    "🛠️ ZAR Admin Menu\n\n"

    "📊 Customer Surveys\n\n"

    "Start survey\n"
    "survey: <question>\n\n"

    "Example\n"
    "survey: How was your experience today?\n\n"

    "End active survey\n"
    "end survey\n\n"

    "Notes\n"
    "• Only one survey can be active\n"
    "• Results are sent when the survey ends\n\n"

    "────────────────\n\n"

    "📣 Announcements\n\n"

    "Option 1 — Text announcement\n"
    "announcement: <text>\n\n"

    "Example\n"
    "announcement: Breakfast special today – free coffee with any meal!\n\n"

    "Option 2 — Image announcement\n"
    "Send an image with an optional caption\n\n"

    "Notes\n"
    "• Only one announcement is active\n"
    "• New announcement replaces the previous one\n\n"

    "Customers can view announcements by typing\n"
    "announcements"
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