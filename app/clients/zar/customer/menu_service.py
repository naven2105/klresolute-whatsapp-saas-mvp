from __future__ import annotations

"""
File: menu_service.py
Path: app/clients/zar/customer/menu_service.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
ZAR customer menu command handling.

Rules:
- Customer-only logic
- No dispatcher logic
- Sends menu image when customer types "food"
- Returns True if handled
"""

import logging
from sqlalchemy.orm import Session

from app.outbound.factory import get_meta_client

logger = logging.getLogger("zar.menu_service")


# --------------------------------------------------
# ZAR MENU IMAGE (Meta media_id required)
# --------------------------------------------------
ZAR_MENU_MEDIA_ID = "REPLACE_WITH_META_MEDIA_ID"


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
            media_id=ZAR_MENU_MEDIA_ID,
        )

        return True

    except Exception:

        logger.exception(
            "ZAR_MENU_SEND_FAIL | to=%s",
            sender_msisdn,
        )

        return True