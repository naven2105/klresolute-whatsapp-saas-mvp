from __future__ import annotations

"""
File: app/clients/galitos/handlers/admin_surveys.py
Path: app/clients/galitos/admin_surveys.py
Project: KLResolute WhatsApp SaaS MVP
"""

import logging
import re
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models import Contact, Conversation, WhatsAppNumber
from app.outbound.factory import get_meta_client
from app.messaging.client_messenger import send_message
from app.profiles.client_profile import get_client_profile

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

logger = logging.getLogger("Galitos admin_surveys")

_SURVEY_TYPED_RE = re.compile(
    r"^\s*survey\s+(sentiment|frequency|helpfulness)\s*:\s*(.+)\s*$",
    re.IGNORECASE,
)

_SURVEY_DEFAULT_RE = re.compile(
    r"^\s*survey\s*:\s*(.+)\s*$",
    re.IGNORECASE,
)


def _sanitize_template_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\n", " ").replace("\t", " ")
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def handle_admin_surveys(
    *,
    db: Session,
    sender_number: str,
    message_text: str,
    business_msisdn: str,
) -> bool:

    logger.info("SURVEY_ENTER | sender=%s | raw=%r", sender_number, message_text)

    try:
        if not is_admin_message(
            db=db,
            sender=sender_number,
            business_msisdn=business_msisdn,
        ):
            logger.info("SURVEY_SKIP | reason=not_admin")
            return False

        meta = get_meta_client(
            db=db,
            business_msisdn=business_msisdn,
        )

        profile = get_client_profile(
            business_msisdn,
            db=db,
        )
        if not profile:
            return False

        text_clean = (message_text or "").strip()
        upper = text_clean.upper()
        business_number = business_msisdn

        # -------------------------------------------------
        # AUTO CLOSE (silent)
        # -------------------------------------------------
        try:
            closed = auto_close_expired_surveys(db, business_number)
            if closed:
                summary = build_survey_summary_text(db, closed)

                send_message(
                    db=db,
                    business_msisdn=business_msisdn,
                    to_number=sender_number,
                    text=_sanitize_template_text(summary),
                )
        except Exception:
            pass

        # -------------------------------------------------
        # CLOSE
        # -------------------------------------------------
        if upper == SURVEY_COMMAND_END:

            active = get_active_survey(db, business_number)
            if not active:
                send_message(
                    db=db,
                    business_msisdn=business_msisdn,
                    to_number=sender_number,
                    text=_sanitize_template_text(
                        ADMIN_SURVEY_NO_ACTIVE_TEMPLATE
                    ),
                )
                return True

            close_survey(db, active, manual=True)
            summary = build_survey_summary_text(db, active)

            send_message(
                db=db,
                business_msisdn=business_msisdn,
                to_number=sender_number,
                text=_sanitize_template_text(summary),
            )

            send_message(
                db=db,
                business_msisdn=business_msisdn,
                to_number=sender_number,
                text="Survey closed successfully.",
            )

            return True

        # -------------------------------------------------
        # START
        # -------------------------------------------------
        m = _SURVEY_TYPED_RE.match(text_clean)
        if m:
            survey_type = m.group(1).upper()
            question = m.group(2).strip()
        else:
            m2 = _SURVEY_DEFAULT_RE.match(text_clean)
            if not m2:
                return False
            survey_type = "SENTIMENT"
            question = m2.group(1).strip()

        active_existing = get_active_survey(db, business_number)
        if active_existing:
            send_message(
                db=db,
                business_msisdn=business_msisdn,
                to_number=sender_number,
                text=_sanitize_template_text(
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
            return True

        # -------------------------------------------------
        # SEND INTERACTIVE (APPROVED EXCEPTION)
        # -------------------------------------------------
        buttons_def = SURVEY_BUTTON_SETS[survey_type]["buttons"]

        # FIX 1: Correct admin lookup using client_code
        admin_numbers = {
            row[0]
            for row in db.execute(
                text(
                    """
                    SELECT msisdn
                    FROM client_admins
                    WHERE LOWER(client_code) = LOWER(:client_code)
                      AND is_active = TRUE
                    """
                ),
                {"client_code": profile.client_code},
            ).all()
        }

        # FIX 2: Tenant-scoped contact selection via conversations
        contacts = (
            db.query(Contact)
            .join(Conversation, Conversation.contact_id == Contact.contact_id)
            .join(
                WhatsAppNumber,
                WhatsAppNumber.wa_number_id == Conversation.wa_number_id,
            )
            .filter(WhatsAppNumber.destination_number == business_msisdn)
            .filter(~Contact.contact_number.in_(admin_numbers))
            .distinct()
            .all()
        )

        for c in contacts:
            meta.send_interactive_button_message(
                to_msisdn=c.contact_number,
                header_text="🗳️ Quick question",
                body_text=question,
                buttons=[{"id": b["id"], "title": b["text"]} for b in buttons_def],
            )

        send_message(
            db=db,
            business_msisdn=business_msisdn,
            to_number=sender_number,
            text=_sanitize_template_text(
                ADMIN_SURVEY_STARTED_TEMPLATE.format(question=question)
            ),
        )

        return True

    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return True