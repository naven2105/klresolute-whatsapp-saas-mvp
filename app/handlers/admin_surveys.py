from __future__ import annotations

"""
File: app/handlers/admin_surveys.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Isolated admin survey lifecycle handling.

Scope (LOCKED):
- Start survey
- Block if active
- Close survey
- Admin notifications
- Customer survey delivery
"""

import logging
import re
from sqlalchemy.orm import Session

from app.models import Contact
from app.outbound.factory import get_meta_client
from app.survey import (
    start_survey,
    get_active_survey,
    close_survey,
    build_survey_summary_text,
    auto_close_expired_surveys,
    SURVEY_COMMAND_END,
)
from app.survey.survey_constants import (
    ADMIN_SURVEY_STARTED_TEMPLATE,
    ADMIN_SURVEY_ALREADY_ACTIVE_TEMPLATE,
    ADMIN_SURVEY_NO_ACTIVE_TEMPLATE,
    SURVEY_BUTTON_SETS,
)

logger = logging.getLogger("admin_surveys")

_SURVEY_TYPED_RE = re.compile(
    r"^\s*survey\s+(sentiment|frequency|helpfulness)\s*:\s*(.+)\s*$",
    re.IGNORECASE,
)

_SURVEY_DEFAULT_RE = re.compile(
    r"^\s*survey\s*:\s*(.+)\s*$",
    re.IGNORECASE,
)


def handle_admin_surveys(
    *,
    db: Session,
    sender_number: str,
    message_text: str,
    admin_allowlist: set[str],
) -> bool:
    """
    Returns True if survey command handled.
    """

    meta = get_meta_client()
    business_number = sender_number

    # -------------------------------
    # AUTO-CLOSE (silent, safe)
    # -------------------------------
    try:
        closed = auto_close_expired_surveys(db, business_number)
        if closed:
            logger.info("AUTO_CLOSED | survey_id=%s", closed.id)
            summary = build_survey_summary_text(db, closed)
            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text=summary,
            )
    except Exception as exc:
        logger.error("AUTO_CLOSE_FAIL | error=%s", exc, exc_info=True)

    # -------------------------------
    # CLOSE SURVEY
    # -------------------------------
    if upper == SURVEY_COMMAND_END:
        logger.info("SURVEY_CLOSE_REQUEST")

        active = get_active_survey(db, business_number)
        if not active:
            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text=ADMIN_SURVEY_NO_ACTIVE_TEMPLATE,
            )
            return True

        close_survey(db, active, manual=True)
        summary = build_survey_summary_text(db, active)

        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text=summary,
        )
        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text="✅ Survey closed successfully.",
        )
        return True

    # -------------------------------
    # START SURVEY (typed)
    # -------------------------------
    m = _SURVEY_TYPED_RE.match(text_clean)
    if not m:
        m = _SURVEY_DEFAULT_RE.match(text_clean)
        if not m:
            return False
        survey_type = "SENTIMENT"
        question = m.group(1).strip()
    else:
        survey_type = m.group(1).upper()
        question = m.group(2).strip()

    logger.info("SURVEY_START | type=%s | question=%r", survey_type, question)

    active_existing = get_active_survey(db, business_number)
    if active_existing:
        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text=ADMIN_SURVEY_ALREADY_ACTIVE_TEMPLATE.format(
                question=active_existing.question,
                hours_remaining=int(
                    (active_existing.ends_at - active_existing.started_at)
                    .total_seconds() / 3600
                ),
            ),
        )
        return True

    started, survey = start_survey(
        db=db,
        business_number=business_number,
        question=question,
        button_set=survey_type,
    )

    buttons_def = SURVEY_BUTTON_SETS[survey_type]["buttons"]
    contacts = (
        db.query(Contact)
        .filter(~Contact.contact_number.in_(admin_allowlist))
        .all()
    )

    for c in contacts:
        meta.send_interactive_button_message(
            to_msisdn=c.contact_number,
            header_text="🗳️ Quick question",
            body_text=question,
            buttons=[{"id": b["id"], "title": b["text"]} for b in buttons_def],
        )

    meta.send_generic_business_update_template(
        to_msisdn=sender_number,
        blob_text=ADMIN_SURVEY_STARTED_TEMPLATE.format(question=question),
    )

    return True
