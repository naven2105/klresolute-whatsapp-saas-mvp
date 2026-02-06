from __future__ import annotations

"""
File: app/handlers/admin_menu_builder.py
Path: app/handlers/admin_menu_builder.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Build the Admin Menu text ONLY.

Scope (LOCKED):
- No DB writes
- No message sending
- No routing
- No client-specific branching
- No UUID / INTEGER handling
- Pure text construction

Design Rules:
- Single source of truth for Admin Menu
- One responsibility: return menu text
- Safe to call from Tier-1
- Guarded with logs
"""

import logging

logger = logging.getLogger("handlers.admin_menu_builder")


def build_admin_menu_text() -> str:
    """
    Returns the full admin menu text.
    This function must NEVER raise.
    """

    try:
        menu = (
            "🛠️ Admin Menu\n\n"
            "📊 Surveys\n"
            "SURVEY SENTIMENT: <question>\n"
            "👍 Like   😐 Neutral   👎 Dislike\n\n"
            "SURVEY FREQUENCY: <question>\n"
            "👍 Like   😐 Neutral   👎 Dislike\n\n"
            "SURVEY HELPFULNESS: <question>\n"
            "👍 Like   😐 Neutral   👎 Dislike\n\n"
            "END SURVEY\n\n"
            "ℹ️ Survey Notes\n"
            "- Surveys auto-close after 24 hours\n"
            "- A new survey replaces any active survey\n"
            "- Survey results are sent to admins on close\n\n"
            "🔥 Specials\n"
            "- Send an image with caption to set a special\n"
            "- Only ONE special is active at a time\n"
            "- New special replaces the previous one\n"
            "- Customers can only see the latest special\n\n"
            "⚙️ System Status\n"
            "STATUS: <message>\n"
            "CLEAR STATUS\n"
        )

        logger.info("ADMIN_MENU_BUILT_OK")
        return menu

    except Exception as exc:
        logger.exception("ADMIN_MENU_BUILD_FAIL | err=%s", exc)

        # Fail-safe minimal menu
        return (
            "🛠️ Admin Menu\n\n"
            "⚠️ Menu temporarily unavailable.\n"
            "Please try again."
        )
