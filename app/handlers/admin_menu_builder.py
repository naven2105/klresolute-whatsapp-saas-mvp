from __future__ import annotations

"""
File: app/handlers/admin_menu_builder.py
Path: app/handlers/admin_menu_builder.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Build and return the Admin Menu text.

Rules (LOCKED):
- Read-only
- No DB writes
- No command handling
- Pure menu composition
- Single source of truth for Admin Menu text
"""

import logging
from sqlalchemy.orm import Session

logger = logging.getLogger("handlers.admin_menu_builder")


def build_admin_menu(*, db: Session, business_msisdn: str) -> str:
    """
    Returns the full Admin Menu text.
    DB is passed for future-proofing (e.g. feature flags),
    but not used for logic at this stage.
    """

    logger.info(
        "ADMIN_MENU_BUILD | business=%s",
        business_msisdn,
    )

    return (
        "🛠️ Admin Menu\n\n"
        "📊 Surveys\n"
        "SENTIMENT → 👍 😐 👎\n"
        "FREQUENCY → DAILY | WEEKLY | MONTHLY\n"
        "HELPFULNESS → YES | NO\n"
        "END SURVEY\n\n"
        "ℹ️ Survey notes:\n"
        "• Surveys automatically close after 24 hours\n"
        "• Starting a new survey within 24 hours will close the previous one\n"
        "• Survey results are shared with admins automatically\n\n"
        "🔥 Specials\n"
        "SPECIALS IMAGE → <send image + caption>\n"
        "CLEAR SPECIALS\n\n"
        "ℹ️ Specials notes:\n"
        "• Only one special can be active at a time\n"
        "• Customers can only access the latest special\n\n"
        "✉️ Messaging\n"
        "SEND: <number> <message>\n\n"
        "ℹ️ Messaging notes:\n"
        "• Messages are sent to one customer at a time\n\n"
        "⚙️ System\n"
        "STATUS: <message>\n"
        "CLEAR STATUS"
    )
