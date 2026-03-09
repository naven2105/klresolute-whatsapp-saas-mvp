from __future__ import annotations

"""
File: menu_service.py
Path: app/clients/zar/customer/menu_service.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
ZAR customer menu command handler.

Rules:
- Customer-only logic
- No dispatcher logic
- Returns menu image (menu.png)
- Returns True if handled
"""

import logging
from sqlalchemy.orm import Session

from app.outbound.factory import get_meta_client

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
            media_id=None,
            caption=None,
        )

        logger.info(
            "ZAR_MENU_SENT | to=%s",
            sender_msisdn,
        )

    except Exception:
        logger.exception(
            "ZAR_MENU_SEND_FAIL | to=%s",
            sender_msisdn,
        )

    return True