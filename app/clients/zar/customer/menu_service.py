from __future__ import annotations

"""
File: menu_service.py
Path: app/clients/zar/customer/menu_service.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
ZAR customer food menu handler.

Rules:
- Customer-only logic
- Uses static WhatsApp media_id from config
- Returns True if handled
"""

import logging
from sqlalchemy.orm import Session

from app.outbound.factory import get_meta_client
from app.config.media_ids import ZAR_FOOD_MENU

logger = logging.getLogger("zar.menu_service")


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

        meta.send_image_message(
            to_msisdn=sender_msisdn,
            media_id=ZAR_FOOD_MENU,
            caption="🍽️ Our Food Menu",
        )

        return True

    except Exception:
        logger.exception(
            "ZAR_MENU_SEND_FAIL | to=%s",
            sender_msisdn,
        )
        return True


def handle_drinks_command(
    *,
    db: Session,
    sender_msisdn: str,
    business_msisdn: str,
    message_text: str,
) -> bool:
    return False