from __future__ import annotations

"""
File: app/handlers/admin_menu.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Admin menu display + fallback handling.

Rules:
- Admin-only
- Any unknown admin command should result in admin menu
- Menu text is the single source of truth
- No business logic here (routing only)
"""

import logging

from sqlalchemy.orm import Session
from app.outbound.factory import get_meta_client

# -------------------------------------------------
# Logging
# -------------------------------------------------
logger = logging.getLogger("admin_menu")


# -------------------------------------------------
# Admin Menu Text (AUTHORITATIVE)
# -------------------------------------------------
ADMIN_MENU_TEXT = (
    "🛠️ Admin Menu\n\n"
    "📊 Surveys (button-based)\n"
    "SURVEY SENTIMENT: <question>\n"
    "  Sentiment (👍 Yes / 😐 Okay / 👎 No)\n\n"
    "SURVEY FREQUENCY: <question>\n"
    "  Frequency (Weekly / Occasionally / First time)\n\n"
    "SURVEY HELPFULNESS: <question>\n"
    "  Helpfulness (Very / Somewhat / Not helpful)\n\n"
    "END SURVEY\n"
    "  Close active survey early\n\n"
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


# -------------------------------------------------
# Handler
# -------------------------------------------------
def handle_admin_menu(
    *,
    db: Session,
    sender_number: str,
    message_text: str,
    admin_allowlist: set[str],
) -> bool:
    """
    Admin menu fallback.

    Behaviour:
    - If admin sends MENU → show menu
    - If admin sends unknown command → show menu
    - If not admin → return False
    """

    logger.info(
        "ADMIN_MENU_ENTER | sender=%s | text=%r",
        sender_number,
        message_text,
    )

    if sender_number not in admin_allowlist:
        logger.info("ADMIN_MENU_SKIP | not admin | sender=%s", sender_number)
        return False

    meta = get_meta_client()
    upper = (message_text or "").strip().upper()

    # Explicit MENU command
    if upper in {"MENU", "HELP", "ADMIN"}:
        logger.info("ADMIN_MENU_EXPLICIT_REQUEST")
        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text=ADMIN_MENU_TEXT,
        )
        return True

    # Fallback: unknown admin command
    logger.warning(
        "ADMIN_MENU_FALLBACK | unknown admin command | text=%r",
        message_text,
    )

    meta.send_generic_business_update_template(
        to_msisdn=sender_number,
        blob_text=ADMIN_MENU_TEXT,
    )

    return True
