from __future__ import annotations

"""
File: menu_service.py
Path: app/clients/zar/customer/menu_service.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
ZAR customer food command handling.

Rules:
- Customer-only logic
- No dispatcher logic
- Static image menu
- Returns True if handled
"""

import logging
from sqlalchemy.orm import Session

from app.outbound.factory import get_meta_client

logger = logging.getLogger("zar.menu_service")


# --------------------------------------------------
# FOOD MENU (STATIC IMAGE)
# --------------------------------------------------
def handle_menu_command(
    *,
    db: Session,
    sender_msisdn: str,
    business_msisdn: str,
    message_text: str,
) -> bool:

    msg = (message_text or "").strip().lower()

    if msg != "food":
        return False

    try:

        meta = get_meta_client(
            db=db,
            business_msisdn=business_msisdn,
        )

        # Static menu image in assets folder
        meta.send_image_file(
            to_msisdn=sender_msisdn,
            image_path="app/assets/menu.png",
            caption="🍽️ Our Food Menu",
        )

        return True

    except Exception:
        logger.exception(
            "ZAR_MENU_SEND_FAIL | to=%s",
            sender_msisdn,
        )
        return True


# --------------------------------------------------
# DRINKS MENU (DISABLED FOR ZAR)
# --------------------------------------------------
def handle_drinks_command(
    *,
    db: Session,
    sender_msisdn: str,
    business_msisdn: str,
    message_text: str,
) -> bool:
    return False