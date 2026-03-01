from __future__ import annotations

"""
File: app/clients/galitos/handlers/admin_surveys.py
Path: app/clients/galitos/handlers/admin_surveys.py
Project: KLResolute WhatsApp SaaS MVP

MVP Survey Simplification:
- Single survey type
- Uses Utility template survey_v1
- END SURVEY returns closure report
"""

import logging
import re
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models import Contact
from app.messaging.client_messenger import send_message
from app.messaging.template_registry import SURVEY_TEMPLATE_V1
from app.profiles.client_profile import get_client_profile
from app.clients.galitos.survey.survey_service import (
    start_survey,
    get_active_survey,
    close_survey,
    auto_close_expired_surveys,
)
from app.clients.galitos.survey.summary import build_survey_summary_text
from app.clients.galitos.survey.survey_constants import (
    ADMIN_SURVEY_STARTED_TEMPLATE,
    ADMIN_SURVEY_ALREADY_ACTIVE_TEMPLATE,
)

from app.utils.admin import is_admin_message

logger = logging.getLogger("Galitos admin_surveys")

_SURVEY_RE = re.compile(
    r"^\s*survey\s*:\s*(.+)\s*$",
    re.IGNORECASE,
)


def _sanitize_template_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\n", " ").replace("\t", " ")
    return re.sub(r"\s{2,}", " ", text).strip()


def handle_admin_surveys(
    *,
    db: Session,
    sender_number: str,
    message_text: str,
    business_msisdn: str,
) -> bool:

    try:
        if not is_admin_message(
            db=db,
            sender=sender_number,
            business_msisdn=business_msisdn,
        ):
            return False

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
        # AUTO CLOSE
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
        # END SURVEY (FIXED)
        # -------------------------------------------------
        if upper == "END SURVEY":

            active = get_active_survey(db, business_number)
            if not active:
                send_message(
                    db=db,
                    business_msisdn=business_msisdn,
                    to_number=sender_number,
                    text="⚠️ No active survey.",
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

            return True

        # -------------------------------------------------
        # START SURVEY
        # -------------------------------------------------
        m = _SURVEY_RE.match(text_clean)
        if not m:
            return False

        question = m.group(1).strip()

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
            button_set="STANDARD",
        )

        if not started or not survey:
            return True

        # -------------------------------------------------
        # SEND TEMPLATE
        # -------------------------------------------------
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

        contacts = (
            db.query(Contact)
            .filter(~Contact.contact_number.in_(admin_numbers))
            .all()
        )

        for c in contacts:
            send_message(
                db=db,
                business_msisdn=business_msisdn,
                to_number=c.contact_number,
                template_name=SURVEY_TEMPLATE_V1,
                template_params=[question],
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