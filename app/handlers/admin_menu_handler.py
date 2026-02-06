from __future__ import annotations

"""
File: app/handlers/admin_menu_handler.py
Path: app/handlers/admin_menu_handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Admin MENU command handler.

Responsibilities:
- Detect admin MENU command
- Authorise admin
- Build admin menu via builder
- Send menu via Meta client

Design rules (LOCKED):
- One responsibility only
- No DB writes
- No menu construction here
- Fail closed if admin check fails
"""

import logging
from sqlalchemy.orm import Session

from app.outbound.factory import get_meta_client
from app.utils.admin import is_admin_message
from app.handlers.admin_menu_builder import build_admin_menu

logger = logging.getLogger("admin_menu_handler")


def handle_admin_menu(
    *,
    db: Session,
    sender_number: str,
    message_text: str,
    business_msisdn: str,
) -> bool:
    """
    Returns True if MENU was handled.
    """

    if message_text.strip().upper() != "MENU":
        return False

    if not is_admin_message(
        db=db,
        sender=sender_number,
        business_msisdn=business_msisdn,
    ):
        logger.info(
            "ADMIN_MENU_REJECT | not admin | sender=%s | business=%s",
            sender_number,
            business_msisdn,
        )
        return True  # handled (blocked)

    try:
        menu_text = build_admin_menu(
            db=db,
            business_msisdn=business_msisdn,
        )

        meta = get_meta_client(business_msisdn=business_msisdn)
        meta.send_session_message(
            to_msisdn=sender_number,
            text=menu_text,
        )

        logger.info(
            "ADMIN_MENU_SENT | sender=%s | business=%s",
            sender_number,
            business_msisdn,
        )
        return True

    except Exception as exc:
        logger.exception(
            "ADMIN_MENU_FAIL | sender=%s | business=%s | err=%s",
            sender_number,
            business_msisdn,
            exc,
        )
        return True
