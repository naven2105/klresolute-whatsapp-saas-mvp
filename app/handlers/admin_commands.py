from __future__ import annotations

"""
File: app/handlers/admin_commands.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Admin command router.

Routing order (LOCKED):
1. admin_surveys
2. admin_messaging
3. admin_menu (fallback)
"""

import logging
from sqlalchemy.orm import Session

from app.handlers.admin_surveys import handle_admin_surveys
from app.handlers.admin_messaging import handle_admin_messaging
from app.handlers.admin_menu import handle_admin_menu

# -------------------------------------------------
# Logging
# -------------------------------------------------
logger = logging.getLogger("admin_commands")


def handle_admin_command(
    *,
    db: Session,
    sender_number: str,
    message_text: str,
    admin_allowlist: set[str],
) -> bool:
    """
    Routes admin commands to the correct handler.

    Returns:
        True  -> handled by admin layer
        False -> not admin / let client flow handle
    """

    logger.info(
        "ADMIN_ROUTER_ENTER | sender=%s | text=%r",
        sender_number,
        message_text,
    )

    if sender_number not in admin_allowlist:
        logger.info("ADMIN_ROUTER_SKIP | not admin | sender=%s", sender_number)
        return False

    # 1️⃣ Surveys
    if handle_admin_surveys(
        db=db,
        sender_number=sender_number,
        message_text=message_text,
        admin_allowlist=admin_allowlist,
    ):
        logger.info("ADMIN_ROUTER_HANDLED | handler=surveys")
        return True

    # 2️⃣ Messaging
    if handle_admin_messaging(
        db=db,
        sender_number=sender_number,
        message_text=message_text,
        admin_allowlist=admin_allowlist,
    ):
        logger.info("ADMIN_ROUTER_HANDLED | handler=messaging")
        return True

    # 3️⃣ Menu fallback (ALWAYS responds)
    handled = handle_admin_menu(
        db=db,
        sender_number=sender_number,
        message_text=message_text,
        admin_allowlist=admin_allowlist,
    )

    logger.info("ADMIN_ROUTER_HANDLED | handler=menu")
    return handled
