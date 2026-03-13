# ==================================================
# File: admin_menu_service.py
# Path: app/clients/rusticbarrel/admin/admin_menu_service.py
# Project: KLResolute WhatsApp SaaS MVP
#
# Purpose:
# RusticBarrel Admin Menu
#
# Rules:
# - Admin only
# - Text only
# - No dispatcher logic
# - Uses RusticBarrel menu configuration
# ==================================================

from __future__ import annotations

from sqlalchemy.orm import Session
from app.messaging.client_messenger import send_message

from app.menus.admin.rusticbarrel_admin_menu import RUSTICBARREL_ADMIN_MENU


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
        text=RUSTICBARREL_ADMIN_MENU["text"],
    )

    return True