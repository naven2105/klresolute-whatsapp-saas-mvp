from __future__ import annotations

"""
File: app/handlers/admin_messaging.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Admin messaging commands only.

Scope (LOCKED):
- Specials
- NO SEND
- NO PAUSE / RESUME
- NO surveys
- NO admin menu text

Rules:
- Admin-facing only
- Explicit logging for every decision
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models import Contact
from app.messaging.client_messenger import send_message
from app.utils.admin import is_admin_message
from app.profiles.client_profile import get_client_profile

logger = logging.getLogger("admin_messaging")


def handle_admin_messaging(
    *,
    db: Session,
    sender_number: str,
    message_text: str,
    business_msisdn: str,
) -> bool:

    logger.info(
        "ADMIN_MSG_ENTER | sender=%s | raw=%r",
        sender_number,
        message_text,
    )

    if not is_admin_message(
        db=db,
        sender=sender_number,
        business_msisdn=business_msisdn,
    ):
        logger.info(
            "ADMIN_MSG_REJECT | sender not admin | sender=%s",
            sender_number,
        )
        return False

    text_body = (message_text or "").strip()
    upper = text_body.upper()

    profile = get_client_profile(business_msisdn, db=db)
    if not profile:
        logger.error("ADMIN_MSG_ABORT | profile_missing")
        return True

    
    logger.info("ADMIN_MSG_UNKNOWN_COMMAND | sender=%s", sender_number)

    send_message(
        db=db,
        business_msisdn=business_msisdn,
        to_number=sender_number,
        text="Unknown admin command.\n\nType MENU to view options.",
    )

    return True
