"""
app/survey/survey_service.py

Survey lifecycle service for KLResolute MVP
-------------------------------------------
Scope: Tier 1 only
Purpose:
- Start surveys
- Prevent overlapping surveys
- Close surveys (manual / auto)
- Record responses
- Generate admin summaries

NO message transport logic here.
NO Meta / WhatsApp payloads here.
"""

from datetime import datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.survey.survey_models import Survey, SurveyResponse
from app.survey.survey_constants import (
    DEFAULT_SURVEY_DURATION_HOURS,
    SURVEY_STATUS_ACTIVE,
    SURVEY_STATUS_CLOSED,
    SURVEY_BUTTON_SETS,
    ADMIN_SURVEY_SUMMARY_TEMPLATE,
)


# -------------------------------------------------
# Survey lifecycle
# -------------------------------------------------

def get_active_survey(
    db: Session,
    business_number: str,
) -> Optional[Survey]:
    return (
        db.query(Survey)
        .filter(
            Survey.business_number == business_number,
            Survey.status == SURVEY_STATUS_ACTIVE,
        )
        .one_or_none()
    )


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
    """
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


def close_survey(
    db: Session,
    survey: Survey,
    manual: bool = False,
) -> Survey:
    """
    Close a survey explicitly or via auto-expiry.
    """
    survey.status = SURVEY_STATUS_CLOSED
    survey.closed_at = datetime.utcnow()

    db.commit()
    db.refresh(survey)

    return survey


def auto_close_expired_surveys(
    db: Session,
    business_number: str,
) -> Optional[Survey]:
    """
    Check if an active survey has expired.
    If yes, close it and return it.
    """
    survey = get_active_survey(db, business_number)
    if not survey:
        return None

    if datetime.utcnow() >= survey.ends_at:
        return close_survey(db, survey)

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
    """
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


# -------------------------------------------------
# Summaries
# -------------------------------------------------

def build_survey_summary_text(
    db: Session,
    survey: Survey,
) -> str:
    """
    Build the admin-facing survey summary message.
    """
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

    results_lines = []
    for b in button_defs:
        results_lines.append(
            f"{b['text']} — {counts[b['id']]}"
        )

    tag_lines = []
    for tag, count in tags.items():
        tag_lines.append(f"{tag}: {count} clients")

    return ADMIN_SURVEY_SUMMARY_TEMPLATE.format(
        question=survey.question,
        total=len(responses),
        results="\n".join(results_lines),
        tags="\n".join(tag_lines),
    )
