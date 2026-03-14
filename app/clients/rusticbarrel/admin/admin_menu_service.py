# ==================================================
# File: admin_menu_service.py
# Path: app/clients/rusticbarrel/admin/admin_menu_service.py
# Project: KLResolute WhatsApp SaaS MVP
#
# Sprint 34 – Rustic Barrel Admin Menu Alignment
#
# Purpose:
# Rustic Barrel Admin Menu
#
# Rules:
# - Admin only
# - Text only
# - No dispatcher logic
# - Mirror ZAR functionality
# ==================================================

from __future__ import annotations

from sqlalchemy.orm import Session
from app.messaging.client_messenger import send_message


ADMIN_MENU_TEXT = (
    "🛠️ Rustic Barrel Admin Menu\n\n"

    "🍔 Food Menu\n\n"

    "Update food menu image\n"
    "Send an image with caption:\n"
    "food\n\n"

    "Example\n"
    "Send image\n"
    "Caption: food\n\n"

    "Notes\n"
    "• Image becomes the current food menu\n"
    "• Customers can view it by typing\n"
    "food\n\n"

    "────────────────\n\n"

    "📊 Customer Surveys\n\n"

    "Start survey\n"
    "SURVEY: <question>\n\n"

    "Example\n"
    "SURVEY: How was your meal today?\n\n"

    "End active survey\n"
    "END SURVEY\n\n"

    "Notes\n"
    "• Only one survey can be active\n"
    "• Results are sent when the survey ends\n\n"

    "────────────────\n\n"

    "📣 Announcements\n\n"

    "Option 1 — Text announcement\n"
    "announcement: <text>\n\n"

    "Example\n"
    "announcement: Lunch special today – 20% off!\n\n"

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