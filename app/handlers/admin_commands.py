from __future__ import annotations

"""
File: app/handlers/admin_commands.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Central admin command router.

RULES (LOCKED):
- This file contains NO business logic
- Delegates to specialised admin handlers
- Order matters:
  1. Surveys
  2. Messaging
  3. Menu (fallback)
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


# -------------------------------------------------
# Router
# -------------------------------------------------

def handle_admin_command(
    *,
    db: Session,
    sender_number: str,
    message_text: str,
    admin_allowlist: set[str],
) -> bool:
    """
    Admin command router.

    Returns:
        True  -> handled as admin
        False -> not an admin command
    """

    logger.info(
        "ADMIN_ROUTER_ENTER | sender=%s | raw=%r",
        sender_number,
        message_text,
    )

    # -------------------------------------------------
    # 1. Surveys
    # -------------------------------------------------
    try:
        if handle_admin_surveys(
            db=db,
            sender_number=sender_number,
            message_text=message_text,
            admin_allowlist=admin_allowlist,
        ):
            logger.info("ADMIN_ROUTER_HANDLED | handler=surveys")
            return True
    except Exception as exc:
        logger.error(
            "ADMIN_ROUTER_SURVEYS_FAIL | error=%s",
            exc,
            exc_info=True,
        )

    # -------------------------------------------------
    # 2. Messaging
    # -------------------------------------------------
    try:
        if handle_admin_messaging(
            db=db,
            sender_number=sender_number,
            message_text=message_text,
            admin_allowlist=admin_allowlist,
        ):
            logger.info("ADMIN_ROUTER_HANDLED | handler=messaging")
            return True
    except Exception as exc:
        logger.error(
            "ADMIN_ROUTER_MESSAGING_FAIL | error=%s",
            exc,
            exc_info=True,
        )

    # -------------------------------------------------
    # 3. Menu (fallback)
    # -------------------------------------------------
    try:
        if handle_admin_menu(
            db=db,
            sender_number=sender_number,
            message_text=message_text,
            admin_allowlist=admin_allowlist,
        ):
            logger.info("ADMIN_ROUTER_HANDLED | handler=menu")
            return True
    except Exception as exc:
        logger.error(
            "ADMIN_ROUTER_MENU_FAIL | error=%s",
            exc,
            exc_info=True,
        )

    logger.info(
        "ADMIN_ROUTER_NO_MATCH | sender=%s",
        sender_number,
    )
    return False
