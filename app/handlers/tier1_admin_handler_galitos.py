from __future__ import annotations

"""
File: app/handlers/tier1_admin_handler_galitos.py
Path: app/handlers/tier1_admin_handler_galitos.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Tier-1 Galitos Admin command handling.

Responsibilities:
- Admin command routing
- Admin fallback behaviour (unrecognised input)
- Admin menu rendering

GUARD RAILS:
- Fail closed
- Never route customer logic
- Always log admin fallthroughs
"""

import logging
from sqlalchemy.orm import Session

from app.outbound.factory import get_meta_client

logger = logging.getLogger("handlers.tier1_admin_handler")


ADMIN_MENU_TEXT = (
    "🛠️ Admin Menu\n\n"
    "📊 Surveys\n"
    "SURVEY SENTIMENT: <question>\n"
    "SURVEY FREQUENCY: <question>\n"
    "SURVEY HELPFULNESS: <question>\n"
    "END SURVEY\n\n"
    "⚙️ System\n"
    "STATUS: <message>\n"
    "CLEAR STATUS"
)


# -------------------------------------------------
# Public entry
# -------------------------------------------------

def handle_admin_command(
    *,
    db: Session,
    sender_number: str,
    message_text: str,
    business_msisdn: str,
) -> bool:
    """
    Handle admin commands.
    Returns True if handled.
    """

    text = (message_text or "").strip()
    upper = text.upper()

    meta = get_meta_client(business_msisdn=business_msisdn)

    logger.info(
        "ADMIN_CMD_ENTER | sender=%s | text=%r | business=%s",
        sender_number,
        text,
        business_msisdn,
    )

    # ----------------------------------
    # Explicit MENU
    # ----------------------------------
    if upper == "MENU":
        meta.send_session_message(
            to_msisdn=sender_number,
            text=ADMIN_MENU_TEXT,
        )
        logger.info("ADMIN_MENU_SENT | sender=%s", sender_number)
        return True

    # ----------------------------------
    # STATUS commands handled elsewhere
    # (kept explicit for clarity)
    # ----------------------------------
    if upper.startswith("STATUS:"):
        logger.info("ADMIN_STATUS_COMMAND_RECEIVED | sender=%s", sender_number)
        return False  # delegated to status module

    if upper == "CLEAR STATUS":
        logger.info("ADMIN_CLEAR_STATUS_RECEIVED | sender=%s", sender_number)
        return False  # delegated to status module

    # ----------------------------------
    # FALLBACK — ALWAYS SHOW ADMIN MENU
    # ----------------------------------
    logger.info(
        "ADMIN_FALLBACK_MENU | sender=%s | text=%r",
        sender_number,
        text,
    )

    meta.send_session_message(
        to_msisdn=sender_number,
        text=ADMIN_MENU_TEXT,
    )
    return True
