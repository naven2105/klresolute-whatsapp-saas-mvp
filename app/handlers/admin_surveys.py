from __future__ import annotations

"""
File: app/handlers/admin_surveys.py
Path: app/handlers/admin_surveys.py
Project: KLResolute WhatsApp SaaS MVP

Role:
Admin-only entry point for Survey lifecycle control.

Responsibilities (LOCKED):
- Start surveys (typed or default)
- Prevent overlapping active surveys
- Close surveys (manual or auto-expiry)
- Trigger admin-facing summaries
- Dispatch interactive surveys to customers

GUARD RAILS:
- Admin-only execution
- Must never raise exceptions to dispatcher
- Must never block non-survey admin commands
- Messaging failures must not break flow

NOTE:
- Survey business logic lives in survey_service
- This file orchestrates only
"""

import logging
import re
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models import Contact
from app.outbound.factory import get_meta_client

from app.modules.survey.survey_service import (
    start_survey,
    get_active_survey,
    close_survey,
    auto_close_expired_surveys,
)
from app.modules.survey.summary import build_survey_summary_text
from app.modules.survey.survey_constants import (
    SURVEY_COMMAND_END,
    ADMIN_SURVEY_STARTED_TEMPLATE,
    ADMIN_SURVEY_ALREADY_ACTIVE_TEMPLATE,
    ADMIN_SURVEY_NO_ACTIVE_TEMPLATE,
    SURVEY_BUTTON_SETS,
)

from app.utils.admin import is_admin_message

# -------------------------------------------------
# Logging
# -------------------------------------------------

logger = logging.getLogger("admin_surveys")

# -------------------------------------------------
# Regex
# -------------------------------------------------

_SURVEY_TYPED_RE = re.compile(
    r"^\s*survey\s+(sentiment|frequency|helpfulness)\s*:\s*(.+)\s*$",
    re.IGNORECASE,
)

_SURVEY_DEFAULT_RE = re.compile(
    r"^\s*survey\s*:\s*(.+)\s*$",
    re.IGNORECASE,
)

# -------------------------------------------------
# Helpers
# -------------------------------------------------

def _sanitize_template_text(text: str) -> str:
    """
    Meta template params MUST:
    - not contain newlines
    - not contain tabs
    - not contain multiple spaces
    """
    if not text:
        return ""

    text = text.replace("\n", " ").replace("\t", " ")
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


# -------------------------------------------------
# Handler
# -------------------------------------------------

def handle_admin_surveys(
    *,
    db: Session,
    sender_number: str,
    message_text: str,
    business_msisdn: str,
) -> bool:
    """
    Handle admin-issued survey commands.
    Returns True if the message was handled.
    Never raises.
    """

    logger.info("SURVEY_ENTER | sender=%s | raw=%r", sender_number, message_text)

    try:
        if not is_admin_message(
            db=db,
            sender=sender_number,
            business_msisdn=business_msisdn,
        ):
            logger.info("SURVEY_SKIP | reason=not_admin")
            return False

        meta = get_meta_client()
        text_clean = (message_text or "").strip()
        upper = text_clean.upper()
        business_number = business_msisdn

        logger.info("SURVEY_CLEAN | clean=%r | upper=%r", text_clean, upper)

        # ----------------------------------
        # AUTO-CLOSE expired survey (silent)
        # ----------------------------------
        try:
            closed = auto_close_expired_surveys(db, business_number)
            if closed:
                logger.info("SURVEY_AUTO_CLOSED | survey_id=%s", closed.id)
                summary = build_survey_summary_text(db, closed)
                meta.send_generic_business_update_template(
                    to_msisdn=sender_number,
                    blob_text=_sanitize_template_text(summary),
                )
        except Exception as exc:
            logger.exception("SURVEY_AUTO_CLOSE_FAIL | err=%s", exc)

        # ----------------------------------
        # CLOSE SURVEY
        # ----------------------------------
        if upper == SURVEY_COMMAND_END:
            logger.info("SURVEY_CLOSE_REQUEST")

            active = get_active_survey(db, business_number)
            if not active:
                meta.send_generic_business_update_template(
                    to_msisdn=sender_number,
                    blob_text=_sanitize_template_text(
                        ADMIN_SURVEY_NO_ACTIVE_TEMPLATE
                    ),
                )
                return True

            close_survey(db, active, manual=True)
            logger.info("SURVEY_CLOSED | survey_id=%s", active.id)

            summary = build_survey_summary_text(db, active)

            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text=_sanitize_template_text(summary),
            )

            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text="Survey closed successfully.",
            )

            return True

        # ----------------------------------
        # START SURVEY (typed / default)
        # ----------------------------------
        m = _SURVEY_TYPED_RE.match(text_clean)
        if m:
            survey_type = m.group(1).upper()
            question = m.group(2).strip()
        else:
            m2 = _SURVEY_DEFAULT_RE.match(text_clean)
            if not m2:
                logger.info("SURVEY_NO_MATCH")
                return False
            survey_type = "SENTIMENT"
            question = m2.group(1).strip()

        logger.info(
            "SURVEY_START_REQUEST | type=%s | question=%r",
            survey_type,
            question,
        )

        active_existing = get_active_survey(db, business_number)
        if active_existing:
            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text=_sanitize_template_text(
                    ADMIN_SURVEY_ALREADY_ACTIVE_TEMPLATE.format(
                        question=active_existing.question,
                        hours_remaining=int(
                            (active_existing.ends_at - active_existing.started_at)
                            .total_seconds()
                            / 3600
                        ),
                    )
                ),
            )
            return True

        started, survey = start_survey(
            db=db,
            business_number=business_number,
            question=question,
            button_set=survey_type,
        )

        if not started or not survey:
            logger.warning("SURVEY_START_FAILED | business=%s", business_number)
            return True

        logger.info("SURVEY_STARTED | survey_id=%s", survey.id)

        # ----------------------------------
        # Send to customers
        # ----------------------------------
        buttons_def = SURVEY_BUTTON_SETS[survey_type]["buttons"]

        admin_numbers = {
            row[0]
            for row in db.execute(
                text(
                    """
                    SELECT msisdn
                    FROM client_admins
                    WHERE client_code = :client
                      AND is_active = TRUE
                    """
                ),
                {"client": business_msisdn},
            ).all()
        }

        contacts = (
            db.query(Contact)
            .filter(~Contact.contact_number.in_(admin_numbers))
            .all()
        )

        logger.info(
            "SURVEY_SEND_BEGIN | survey_id=%s | recipients=%s",
            survey.id,
            len(contacts),
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
            blob_text=_sanitize_template_text(
                ADMIN_SURVEY_STARTED_TEMPLATE.format(question=question)
            ),
        )

        logger.info("SURVEY_ADMIN_CONFIRM_SENT | survey_id=%s", survey.id)
        return True

    except Exception as exc:
        logger.exception(
            "SURVEY_HANDLER_FATAL | sender=%s | err=%s",
            sender_number,
            exc,
        )
        try:
            db.rollback()
        except Exception:
            pass
        return True
