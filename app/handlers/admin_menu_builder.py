from __future__ import annotations

"""
File: app/handlers/admin_menu_builder.py
Path: app/handlers/admin_menu_builder.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Build a single, consistent Admin Menu text block.

Scope (LOCKED):
- Read-only
- No DB writes
- No WhatsApp sending
- No routing
- Pure text composition

Design rules:
- One admin menu for all admins
- Survey buttons shown with emojis + labels
- Behavioural notes included (no logic here)
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger("admin_menu_builder")


# -------------------------------------------------
# Constants
# -------------------------------------------------

SURVEY_EMOJI_ROW = "👍 Like   😐 Neutral   👎 Dislike"

SURVEY_NOTE = (
    "ℹ️ Surveys auto-close after 24 hours.\n"
    "ℹ️ Starting a new survey replaces the previous one.\n"
    "ℹ️ Survey results are shared with admins when the survey closes."
)

SPECIALS_NOTE = (
    "ℹ️ Only ONE special can be active at a time.\n"
    "ℹ️ A new special replaces the previous one.\n"
    "ℹ️ Customers can only view the latest special.\n"
    "ℹ️ Specials are sent to ONE customer at a time."
)


# -------------------------------------------------
# Public builder
# -------------------------------------------------

def build_admin_menu(*, db: Session, business_msisdn: str) -> str:
    """
    Build and return the full admin menu text.
    """

    logger.info(
        "ADMIN_MENU_BUILD_START | business=%s",
        business_msisdn,
    )

    survey_block = _build_survey_block(db=db, business_msisdn=business_msisdn)
    system_block = _build_system_block()

    menu = (
        "🛠️ Admin Menu\n\n"
        f"{survey_block}\n\n"
        f"{system_block}"
    )

    logger.info(
        "ADMIN_MENU_BUILD_COMPLETE | business=%s",
        business_msisdn,
    )

    return menu


# -------------------------------------------------
# Blocks
# -------------------------------------------------

def _build_survey_block(*, db: Session, business_msisdn: str) -> str:
    """
    Survey section of the admin menu.
    """

    try:
        active_count = (
            db.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM surveys
                    WHERE is_active = TRUE
                    """
                )
            )
            .scalar()
        )
    except Exception:
        logger.exception(
            "ADMIN_MENU_SURVEY_BLOCK_FAIL | business=%s",
            business_msisdn,
        )
        active_count = 0

    active_line = (
        "🟢 Active survey running"
        if active_count
        else "⚪ No active survey"
    )

    return (
        "📊 Surveys\n"
        f"{active_line}\n\n"
        "Start surveys:\n"
        "SURVEY SENTIMENT: <question>\n"
        "SURVEY FREQUENCY: <question>\n"
        "SURVEY HELPFULNESS: <question>\n"
        "END SURVEY\n\n"
        f"{SURVEY_EMOJI_ROW}\n\n"
        f"{SURVEY_NOTE}"
    )


def _build_system_block() -> str:
    """
    System / status section.
    """

    return (
        "⚙️ System\n"
        "STATUS: <message>\n"
        "CLEAR STATUS\n\n"
        "🎯 Specials\n"
        f"{SPECIALS_NOTE}"
    )
