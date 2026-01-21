from __future__ import annotations

"""
File: app/handlers/admin_menu.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Admin menu handling only.

Scope (LOCKED):
- Show admin menu
- Fallback for unknown admin commands
- NO surveys
- NO messaging logic

Rules:
- Admin-facing only
- Any unknown admin input MUST return the admin menu
"""

import logging
from sqlalchemy.orm import Session

from app.outbound.factory import get_meta_client

# -------------------------------------------------
# Logging
# -------------------------------------------------

logger = logging.getLogger("admin_menu")


# -------------------------------------------------
# Admin Menu Text (SINGLE SOURCE)
# -------------------------------------------------

ADMIN_MENU_TEXT = (
    "🛠️ Admin Menu\n\n"
    "📊 Surveys (button-based)\n"
    "SURVEY SENTIMENT: <question> – Sentiment (👍 Yes / 😐 Okay / 👎 No)\n"
    "SURVEY FREQUENCY: <question> – Frequency (Weekly / Occasionally / First time)\n"
    "SURVEY HELPFULNESS: <question> – Helpfulness (Very / Somewhat / Not helpful)\n"
    "END SURVEY – Close active survey early\n\n"
    "👥 Clients\n"
    "ADD CLIENT: <number>\n"
    "REMOVE CLIENT: <number>\n"
    "COUNT – Active clients\n\n"
    "✉️ Messaging\n"
    "SEND: <number> <message>\n"
    "BROADCAST: <message>  (text only)\n\n"
    "🖼️ Specials\n"
    "Send image + caption – Updates specials (push + replay)\n\n"
    "⚙️ System\n"
    "PAUSE – Stop outbound messages\n"
    "RESUME – Resume outbound messages"
)


# -------------------------------------------------
# Entry point
# -------------------------------------------------

def handle_admin_menu(
    *,
    db: Session,
    sender_number: str,
    message_text: str,
    admin_allowlist: set[str],
) -> bool:
    """
    Handles admin menu display and fallback.

    Returns:
        True  -> menu shown
        False -> not an admin
    """

    logger.info(
        "ADMIN_MENU_ENTER | sender=%s | raw=%r",
        sender_number,
        message_text,
    )

    if sender_number not in admin_allowlist:
        logger.info(
            "ADMIN_MENU_REJECT | sender not admin | sender=%s",
            sender_number,
        )
        return False

    meta = get_meta_client()

    # Always show menu for admin fallback
    try:
        meta.send_session_message(
            to_msisdn=sender_number,
            text=ADMIN_MENU_TEXT,
        )
        logger.info("ADMIN_MENU_SENT_OK | sender=%s", sender_number)
    except Exception as exc:
        logger.error(
            "ADMIN_MENU_SEND_FAIL | sender=%s | error=%s",
            sender_number,
            exc,
            exc_info=True,
        )

    return True
