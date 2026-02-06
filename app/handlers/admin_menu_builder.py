from __future__ import annotations

"""
File: app/handlers/admin_menu_builder.py
Path: app/handlers/admin_menu_builder.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Build the Admin Menu dynamically.

Responsibilities (SINGLE):
- Read active surveys for a business
- Render survey questions WITH their buttons
- Append System commands (Status / Clear Status)
- Return a single menu text block

Rules (LOCKED):
- Read-only DB access
- No message sending
- No routing decisions
- Fail closed (return minimal menu on error)
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger("handlers.admin_menu_builder")


# -------------------------------------------------
# Public API
# -------------------------------------------------

def build_admin_menu(*, db: Session, business_msisdn: str) -> str:
    """
    Build the full admin menu text.

    Always returns a string.
    Never raises.
    """

    try:
        survey_block = _build_survey_block(db=db, business_msisdn=business_msisdn)
    except Exception:
        logger.exception(
            "ADMIN_MENU_SURVEY_BLOCK_FAIL | business=%s",
            business_msisdn,
        )
        survey_block = _empty_survey_block()

    menu = (
        "🛠️ Admin Menu\n\n"
        f"{survey_block}\n\n"
        "⚙️ System\n"
        "STATUS: <message>\n"
        "CLEAR STATUS"
    )

    logger.info(
        "ADMIN_MENU_BUILT | business=%s | surveys_present=%s",
        business_msisdn,
        "yes" if survey_block.strip() else "no",
    )

    return menu


# -------------------------------------------------
# Internal helpers
# -------------------------------------------------

def _build_survey_block(*, db: Session, business_msisdn: str) -> str:
    """
    Render all active surveys with their buttons.
    """

    surveys = (
        db.execute(
            text(
                """
                SELECT
                    s.id            AS survey_id,
                    s.question      AS question
                FROM surveys s
                WHERE s.business_msisdn = :business
                  AND s.is_active = TRUE
                ORDER BY s.created_at
                """
            ),
            {"business": business_msisdn},
        )
        .mappings()
        .all()
    )

    if not surveys:
        return _empty_survey_block()

    lines: list[str] = ["📊 Surveys"]

    for s in surveys:
        buttons = _load_survey_buttons(
            db=db,
            survey_id=s["survey_id"],
        )

        lines.append(f"{s['question']}")

        for b in buttons:
            lines.append(f"  • {b}")

        lines.append("")  # spacing between surveys

    lines.append("END SURVEY")

    return "\n".join(lines).strip()


def _load_survey_buttons(*, db: Session, survey_id: int) -> list[str]:
    """
    Load button labels for a survey.
    """

    rows = (
        db.execute(
            text(
                """
                SELECT label
                FROM survey_buttons
                WHERE survey_id = :survey_id
                ORDER BY position
                """
            ),
            {"survey_id": survey_id},
        )
        .scalars()
        .all()
    )

    return list(rows)


def _empty_survey_block() -> str:
    return (
        "📊 Surveys\n"
        "(no active surveys)"
    )
