from __future__ import annotations

"""
File: app/handlers/admin_menu.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Admin menu handling.

Rules:
- Admin-only
- Any unknown admin command falls back here
- Menu is informational only (no side effects)
- Admin replies use TEMPLATE messages only
"""

import logging
from sqlalchemy.orm import Session

from app.outbound.factory import get_meta_client

logger = logging.getLogger("admin_menu")


ADMIN_MENU_TEXT = (
    "🛠️ Admin Menu\n\n"
    "📊 Surveys (button-based)\n"
    "SURVEY SENTIMENT: <question>\n"
    "  Sentiment (👍 Yes / 😐 Okay / 👎 No)\n\n"
    "SURVEY FREQUENCY: <question>\n"
    "  Frequency (Weekly / Occasionally / First time)\n\n"
    "SURVEY HELPFULNESS: <question>\n"
    "  Helpfulness (Very / Somewhat / Not helpful)\n\n"
    "END SURVEY – Close active survey early\n\n"
    "👥 Clients\n"
    "ADD CLIENT: <number>\n"
    "REMOVE CLIENT: <number>\n"
    "COUNT – Active clients\n\n"
    "✉️ Messaging\n"
    "SEND: <number> <message>\n"
    "BROADCAST: <message>\n\n"
    "⚙️ System\n"
    "PAUSE – Stop outbound messages\n"
    "RESUME – Resume outbound messages"
)


def handle_admin_menu(
    *,
    db: Session,
    sender_number: str,
    text_clean: str,
    admin_allowlist: set[str],
) -> bool:
    """
    Fallback admin menu handler.

    Always returns True for admin numbers.
    """

    if sender_number not in admin_allowlist:
        logger.debug("ADMIN_MENU_REJECT | sender=%s", sender_number)
        return False

    logger.info(
        "ADMIN_MENU_SHOW | sender=%s | trigger=%r",
        sender_number,
        text_clean,
    )

    meta = get_meta_client()

    meta.send_generic_business_update_template(
        to_msisdn=sender_number,
        blob_text=ADMIN_MENU_TEXT,
    )

    return True
