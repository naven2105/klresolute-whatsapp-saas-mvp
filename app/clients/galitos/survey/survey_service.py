from __future__ import annotations

"""
File: app/modules/survey/survey_service.py
Path: app/modules/survey/survey_service.py
Project: KLResolute WhatsApp SaaS MVP

Role:
Survey lifecycle service (Tier-1, DB-backed).

This file contains the authoritative survey lifecycle logic and is
invoked by higher-level handlers and compatibility wrappers.

RESPONSIBILITIES (LOCKED):
- Start surveys
- Prevent overlapping surveys
- Close surveys (manual / auto-expiry)
- Record survey responses
- Build admin-facing survey summaries

GUARD RAILS:
- No message transport
- No Meta / WhatsApp payloads
- No raising exceptions to callers
- Always return safe defaults on failure

Existing logic is preserved exactly.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.clients.galitos.survey.survey_models import Survey, SurveyResponse
from app.clients.galitos.survey.survey_constants import (
    DEFAULT_SURVEY_DURATION_HOURS,
    SURVEY_STATUS_ACTIVE,
    SURVEY_STATUS_CLOSED,
    SURVEY_BUTTON_SETS,
    ADMIN_SURVEY_SUMMARY_TEMPLATE,
)

logger = logging.getLogger("module.survey.survey_service")


# -------------------------------------------------
# Survey lifecycle
# -------------------------------------------------

def get_active_survey(
    db: Session,
    business_number: str,
) -> Optional[Survey]:
    """
    Return the active survey for a business, if any.
    Never raises.
    """
    try:
        return (
            db.query(Survey)
            .filter(
                Survey.business_number == business_number,
                Survey.status == SURVEY_STATUS_ACTIVE,
            )
            .one_or_none()
        )
    except Exception as exc:
        logger.exception(
            "SURVEY_GET_ACTIVE_FAILED | business=%s | err=%s",
            business_number,
            exc,
        )
        return None


def start_survey(
    db: Session,
    business_number: str,
    question: str,
    button_set: str,
) -> Tuple[bool, Optional[Survey]]:
    """
    Attempt to start a new survey.

    Returns:
        (started, survey)
        - started = False if a survey is already active
    Never raises.
    """
    try:
        active = get_active_survey(db, business_number)
        if active:
            return False, active

        now = datetime.utcnow()
        ends_at = now + timedelta(hours=DEFAULT_SURVEY_DURATION_HOURS)

        survey = Survey(
            business_number=business_number,
            question=question,
            button_set=button_set,
            status=SURVEY_STATUS_ACTIVE,
            started_at=now,
            ends_at=ends_at,
        )

        db.add(survey)
        db.commit()
        db.refresh(survey)

        return True, survey

    except Exception as exc:
        logger.exception(
            "SURVEY_START_FAILED | business=%s | err=%s",
            business_number,
            exc,
        )
        try:
            db.rollback()
        except Exception:
            pass
        return False, None


def close_survey(
    db: Session,
    survey: Survey,
    manual: bool = False,
) -> Survey:
    """
    Close a survey explicitly or via auto-expiry.
    Never raises.
    """
    try:
        survey.status = SURVEY_STATUS_CLOSED
        survey.closed_at = datetime.utcnow()

        db.commit()
        db.refresh(survey)

        return survey

    except Exception as exc:
        logger.exception(
            "SURVEY_CLOSE_FAILED | survey_id=%s | manual=%s | err=%s",
            getattr(survey, "id", None),
            manual,
            exc,
        )
        try:
            db.rollback()
        except Exception:
            pass
        return survey


def auto_close_expired_surveys(
    db: Session,
    business_number: str,
) -> Optional[Survey]:
    """
    Close active survey if expired.
    Never raises.
    """
    try:
        survey = get_active_survey(db, business_number)
        if not survey:
            return None

        if datetime.utcnow() >= survey.ends_at:
            return close_survey(db, survey)

        return None

    except Exception as exc:
        logger.exception(
            "SURVEY_AUTO_CLOSE_FAILED | business=%s | err=%s",
            business_number,
            exc,
        )
        return None


# -------------------------------------------------
# Responses
# -------------------------------------------------

def record_response(
    db: Session,
    survey: Survey,
    client_number: str,
    button_id: str,
) -> bool:
    """
    Record a survey response.
    Returns False if the client already responded.
    Never raises.
    """
    try:
        existing = (
            db.query(SurveyResponse)
            .filter(
                SurveyResponse.survey_id == survey.id,
                SurveyResponse.client_number == client_number,
            )
            .one_or_none()
        )

        if existing:
            return False

        button_definitions = SURVEY_BUTTON_SETS[survey.button_set]["buttons"]
        tag = next(
            b["tag"] for b in button_definitions if b["id"] == button_id
        )

        response = SurveyResponse(
            survey_id=survey.id,
            client_number=client_number,
            button_id=button_id,
            tag=tag,
        )

        db.add(response)
        db.commit()

        return True

    except Exception as exc:
        logger.exception(
            "SURVEY_RECORD_RESPONSE_FAILED | survey_id=%s | client=%s | button=%s | err=%s",
            getattr(survey, "id", None),
            client_number,
            button_id,
            exc,
        )
        try:
            db.rollback()
        except Exception:
            pass
        return False


# -------------------------------------------------
# Summaries
# -------------------------------------------------

def build_survey_summary_text(
    db: Session,
    survey: Survey,
) -> str:
    """
    Build admin-facing survey summary text.
    Never raises.
    """
    try:
        responses = (
            db.query(SurveyResponse)
            .filter(SurveyResponse.survey_id == survey.id)
            .all()
        )

        button_defs = SURVEY_BUTTON_SETS[survey.button_set]["buttons"]

        counts = {b["id"]: 0 for b in button_defs}
        tags = {b["tag"]: 0 for b in button_defs}

        for r in responses:
            counts[r.button_id] += 1
            tags[r.tag] += 1

        results_lines = [
            f"{b['text']} — {counts[b['id']]}"
            for b in button_defs
        ]

        tag_lines = [
            f"{tag}: {count} clients"
            for tag, count in tags.items()
        ]

        return ADMIN_SURVEY_SUMMARY_TEMPLATE.format(
            question=survey.question,
            total=len(responses),
            results="\n".join(results_lines),
            tags="\n".join(tag_lines),
        )

    except Exception as exc:
        logger.exception(
            "SURVEY_SUMMARY_BUILD_FAILED | survey_id=%s | err=%s",
            getattr(survey, "id", None),
            exc,
        )
        return ""
