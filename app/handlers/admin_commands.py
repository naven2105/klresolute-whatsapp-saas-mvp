from __future__ import annotations

"""
File: app/handlers/admin_commands.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Admin command router.

Responsibilities (ONLY):
- Admin allowlist gate
- Normalise input
- Route admin commands to:
    1. admin_surveys
    2. admin_messaging
    3. admin_menu (fallback)
- Guarantee admin always receives a response

⚠️ NO BUSINESS LOGIC LIVES HERE
"""

import logging
from sqlalchemy.orm import Session

from app.outbound.factory import get_meta_client

# -------------------------------------------------
# Logging
# -------------------------------------------------
logger = logging.getLogger("admin_commands")

# -------------------------------------------------
# Routed handlers
# -------------------------------------------------
from app.handlers.admin_surveys import handle_admin_surveys
from app.handlers.admin_messaging import handle_admin_messaging
from app.handlers.admin_menu import handle_admin_menu


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
    Routes admin commands to the correct handler.

    Returns:
        True  -> admin command handled
        False -> not an admin (caller should fall back to client handler)
    """

    logger.info(
        "ADMIN_ROUTER_ENTER | sender=%s | raw=%r",
        sender_number,
        message_text,
    )

    # -----------------------------
    # Admin gate
    # -----------------------------
    if sender_number not in admin_allowlist:
        logger.info(
            "ADMIN_ROUTER_REJECT | sender not in allowlist | sender=%s",
            sender_number,
        )
        return False

    text_clean = (message_text or "").strip()
    logger.info(
        "ADMIN_ROUTER_CLEAN | sender=%s | clean=%r",
        sender_number,
        text_clean,
    )

    # Ensure Meta client initialises (fail-fast logging)
    try:
        _ = get_meta_client()
    except Exception as exc:
        logger.error(
            "ADMIN_ROUTER_META_INIT_FAIL | error=%s",
            exc,
            exc_info=True,
        )

    # -----------------------------
    # 1️⃣ Surveys (highest priority)
    # -----------------------------
    try:
        if handle_admin_surveys(
            db=db,
            sender_number=sender_number,
            message_text=text_clean,
            admin_allowlist=admin_allowlist,
        ):
            logger.info(
                "ADMIN_ROUTER_EXIT | handler=admin_surveys | sender=%s",
                sender_number,
            )
            return True
    except Exception as exc:
        logger.error(
            "ADMIN_ROUTER_SURVEYS_FAIL | error=%s",
            exc,
            exc_info=True,
        )

    # -----------------------------
    # 2️⃣ Messaging / system
    # -----------------------------
    try:
        if handle_admin_messaging(
            db=db,
            sender_number=sender_number,
            message_text=text_clean,
            admin_allowlist=admin_allowlist,
        ):
            logger.info(
                "ADMIN_ROUTER_EXIT | handler=admin_messaging | sender=%s",
                sender_number,
            )
            return True
    except Exception as exc:
        logger.error(
            "ADMIN_ROUTER_MESSAGING_FAIL | error=%s",
            exc,
            exc_info=True,
        )

    # -----------------------------
    # 3️⃣ Fallback admin menu
    # -----------------------------
    logger.info(
        "ADMIN_ROUTER_FALLBACK | handler=admin_menu | sender=%s",
        sender_number,
    )

    return handle_admin_menu(
        db=db,
        sender_number=sender_number,
        message_text=text_clean,
        admin_allowlist=admin_allowlist,
    )
