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

# -------------------------------
# Regex
# -------------------------------

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

    logger.info(
        "ADMIN_SURVEYS_ENTER | sender=%s | raw=%r",
        sender_number,
        message_text,
    )

    meta = get_meta_client()
    business_number = sender_number

    # -------------------------------
    # NORMALISE TEXT (FIX)
    # -------------------------------
    text_clean = (message_text or "").strip()
    upper = text_clean.upper()

    logger.info(
        "ADMIN_SURVEYS_TEXT | clean=%r | upper=%r",
        text_clean,
        upper,
    )

    # -------------------------------
    # AUTO-CLOSE (silent, safe)
    # -------------------------------
    try:
        closed = auto_close_expired_surveys(db, business_number)
        if closed:
            logger.info("ADMIN_SURVEYS_AUTO_CLOSED | survey_id=%s", closed.id)
            summary = build_survey_summary_text(db, closed)
            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text=summary,
            )
            logger.info("ADMIN_SURVEYS_AUTO_CLOSED_NOTIFY_OK | survey_id=%s", closed.id)
    except Exception as exc:
        logger.error("ADMIN_SURVEYS_AUTO_CLOSE_FAIL | error=%s", exc, exc_info=True)

    # -------------------------------
    # CLOSE SURVEY
    # -------------------------------
    if upper == SURVEY_COMMAND_END:
        logger.info("ADMIN_SURVEYS_CLOSE_REQUEST")

        active = get_active_survey(db, business_number)
        if not active:
            logger.warning("ADMIN_SURVEYS_CLOSE_NO_ACTIVE")
            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text=ADMIN_SURVEY_NO_ACTIVE_TEMPLATE,
            )
            return True

        close_survey(db, active, manual=True)
        logger.info("ADMIN_SURVEYS_CLOSED | survey_id=%s", active.id)

        summary = build_survey_summary_text(db, active)

        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text=summary,
        )
        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text="✅ Survey closed successfully.",
        )

        logger.info("ADMIN_SURVEYS_CLOSE_NOTIFY_OK | survey_id=%s", active.id)
        return True

    # -------------------------------
    # START SURVEY (typed or default)
    # -------------------------------
    m = _SURVEY_TYPED_RE.match(text_clean)
    if not m:
        m = _SURVEY_DEFAULT_RE.match(text_clean)
        if not m:
            logger.info("ADMIN_SURVEYS_NO_MATCH | ignored")
            return False
        survey_type = "SENTIMENT"
        question = m.group(1).strip()
    else:
        survey_type = m.group(1).upper()
        question = m.group(2).strip()

    logger.info(
        "ADMIN_SURVEYS_START_REQUEST | type=%s | question=%r",
        survey_type,
        question,
    )

    # -------------------------------
    # BLOCK if active
    # -------------------------------
    active_existing = get_active_survey(db, business_number)
    if active_existing:
        logger.warning(
            "ADMIN_SURVEYS_BLOCKED_ACTIVE | active_survey_id=%s",
            active_existing.id,
        )
        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text=ADMIN_SURVEY_ALREADY_ACTIVE_TEMPLATE.format(
                question=active_existing.question,
                hours_remaining=int(
                    (active_existing.ends_at - active_existing.started_at)
                    .total_seconds()
                    / 3600
                ),
            ),
        )
        return True

    # -------------------------------
    # START SURVEY
    # -------------------------------
    started, survey = start_survey(
        db=db,
        business_number=business_number,
        question=question,
        button_set=survey_type,
    )

    logger.info(
        "ADMIN_SURVEYS_STARTED | survey_id=%s | recipients_prepare",
        survey.id,
    )

    buttons_def = SURVEY_BUTTON_SETS[survey_type]["buttons"]
    contacts = (
        db.query(Contact)
        .filter(~Contact.contact_number.in_(admin_allowlist))
        .all()
    )

    sent = 0
    for c in contacts:
        meta.send_interactive_button_message(
            to_msisdn=c.contact_number,
            header_text="🗳️ Quick question",
            body_text=question,
            buttons=[{"id": b["id"], "title": b["text"]} for b in buttons_def],
        )
        sent += 1

    logger.info(
        "ADMIN_SURVEYS_CLIENT_SEND_DONE | survey_id=%s | sent=%s",
        survey.id,
        sent,
    )

    meta.send_generic_business_update_template(
        to_msisdn=sender_number,
        blob_text=ADMIN_SURVEY_STARTED_TEMPLATE.format(question=question),
    )

    logger.info(
        "ADMIN_SURVEYS_ADMIN_CONFIRM_OK | survey_id=%s",
        survey.id,
    )

    return True
