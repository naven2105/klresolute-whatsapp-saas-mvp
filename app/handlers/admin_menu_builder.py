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

Rules:
- One admin menu for all admins
- Survey buttons shown with emojis + labels (per survey type)
- Notes included (surveys + specials)
- Must match DB schema (no assumptions)
"""

import logging
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger("admin_menu_builder")

# -------------------------------------------------
# Survey button rows (menu guidance only)
# -------------------------------------------------
_SURVEY_ROWS: dict[str, str] = {
    "SENTIMENT": "👍 Like   😐 Neutral   👎 Dislike",
    "FREQUENCY": "🔁 Often   ➖ Sometimes   ⏳ Rarely",
    "HELPFULNESS": "✅ Helpful   😐 Neutral   ❌ Not Helpful",
}

# -------------------------------------------------
# Notes (approved wording)
# -------------------------------------------------
_SURVEY_NOTES = (
    "Notes:\n"
    "• Surveys auto-close in 24 hours\n"
    "• Starting a new survey closes the previous one\n"
    "• Survey results are shared with admins when the survey closes"
)

_SPECIALS_NOTES = (
    "Notes:\n"
    "• Only ONE special at a time\n"
    "• A new special replaces the previous one\n"
    "• Customers can only access the latest special\n"
    "• Send to a single customer only"
)


# -------------------------------------------------
# Public builder
# -------------------------------------------------
def build_admin_menu(*, db: Session, business_msisdn: str) -> str:
    """
    Build and return the full admin menu text.

    Guard rails:
    - Never throw (admin must always receive a menu)
    - Log failures loudly
    """
    logger.info("ADMIN_MENU_BUILD_START | business=%s", business_msisdn)

    try:
        survey_block = _build_survey_block(db=db, business_msisdn=business_msisdn)
    except Exception:
        logger.exception("ADMIN_MENU_SURVEY_BLOCK_FATAL | business=%s", business_msisdn)
        survey_block = _build_survey_block_fallback()

    try:
        system_block = _build_system_block()
    except Exception:
        logger.exception("ADMIN_MENU_SYSTEM_BLOCK_FATAL | business=%s", business_msisdn)
        system_block = "⚙️ System\nSTATUS: <message>\nCLEAR STATUS"

    try:
        specials_block = _build_specials_block()
    except Exception:
        logger.exception("ADMIN_MENU_SPECIALS_BLOCK_FATAL | business=%s", business_msisdn)
        specials_block = "🎯 Specials\nSPECIAL: <caption>\n" + _SPECIALS_NOTES

    menu = (
        "🛠️ Admin Menu\n\n"
        f"{survey_block}\n\n"
        "────────────────\n\n"
        f"{specials_block}\n\n"
        "────────────────\n\n"
        f"{system_block}"
    )

    logger.info("ADMIN_MENU_BUILD_COMPLETE | business=%s", business_msisdn)
    return menu


# -------------------------------------------------
# Blocks
# -------------------------------------------------
def _build_survey_block(*, db: Session, business_msisdn: str) -> str:
    """
    Survey section.

    Schema confirmed:
    surveys:
      - business_number (varchar)
      - status (varchar)
      - started_at, ends_at, closed_at
    No is_active, no created_at.
    """

    active = None

    try:
        active = (
            db.execute(
                text(
                    """
                    SELECT
                        id,
                        question,
                        button_set,
                        status,
                        started_at,
                        ends_at,
                        closed_at
                    FROM surveys
                    WHERE business_number = :business
                      AND closed_at IS NULL
                      AND ends_at > :now_ts
                    ORDER BY started_at DESC
                    LIMIT 1
                    """
                ),
                {"business": business_msisdn, "now_ts": datetime.now()},
            )
            .mappings()
            .first()
        )
    except Exception:
        logger.exception("ADMIN_MENU_SURVEY_ACTIVE_QUERY_FAIL | business=%s", business_msisdn)

    if active:
        active_line = (
            f"🟢 Active survey running:\n"
            f"• Type: {str(active.get('button_set') or '').upper()}\n"
            f"• Question: {str(active.get('question') or '').strip()}"
        )
    else:
        active_line = "⚪ No active survey"

    return (
        "📊 Surveys\n"
        f"{active_line}\n\n"
        "Start surveys (one active at a time):\n\n"
        "SURVEY SENTIMENT: <question>\n"
        f"{_SURVEY_ROWS['SENTIMENT']}\n\n"
        "SURVEY FREQUENCY: <question>\n"
        f"{_SURVEY_ROWS['FREQUENCY']}\n\n"
        "SURVEY HELPFULNESS: <question>\n"
        f"{_SURVEY_ROWS['HELPFULNESS']}\n\n"
        "END SURVEY\n\n"
        f"{_SURVEY_NOTES}"
    )


def _build_survey_block_fallback() -> str:
    """
    Fallback survey block if DB query fails.
    Must still show full commands + emoji rows.
    """
    return (
        "📊 Surveys\n"
        "⚪ Survey status unavailable (DB read error)\n\n"
        "Start surveys (one active at a time):\n\n"
        "SURVEY SENTIMENT: <question>\n"
        f"{_SURVEY_ROWS['SENTIMENT']}\n\n"
        "SURVEY FREQUENCY: <question>\n"
        f"{_SURVEY_ROWS['FREQUENCY']}\n\n"
        "SURVEY HELPFULNESS: <question>\n"
        f"{_SURVEY_ROWS['HELPFULNESS']}\n\n"
        "END SURVEY\n\n"
        f"{_SURVEY_NOTES}"
    )


def _build_specials_block() -> str:
    """
    Specials section (menu guidance only).
    No DB reads here.
    """
    return (
        "🎯 Specials\n"
        "SPECIAL: <caption>\n\n"
        f"{_SPECIALS_NOTES}"
    )


def _build_system_block() -> str:
    """
    System / status section.
    """
    return (
        "⚙️ System\n"
        "STATUS: <message>\n"
        "CLEAR STATUS"
    )
