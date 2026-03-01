from __future__ import annotations

"""
File: app/modules/survey/lifecycle.py
Path: app/modules/survey/lifecycle.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Survey lifecycle service (module-authoritative).

Rules:
- DB lifecycle only
- No messaging
- No Meta client usage
"""

from datetime import datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.clients.galitos.survey.models import Survey, SurveyResponse
from app.clients.galitos.survey.constants import (
    DEFAULT_SURVEY_DURATION_HOURS,
    SURVEY_STATUS_ACTIVE,
    SURVEY_STATUS_CLOSED,
    SURVEY_BUTTON_SETS,
    ADMIN_SURVEY_SUMMARY_TEMPLATE,
)


def get_active_survey(db: Session, business_number: str) -> Optional[Survey]:
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


def close_survey(db: Session, survey: Survey, manual: bool = False) -> Survey:
    survey.status = SURVEY_STATUS_CLOSED
    survey.closed_at = datetime.utcnow()
    db.commit()
    db.refresh(survey)
    return survey


def auto_close_expired_surveys(db: Session, business_number: str) -> Optional[Survey]:
    survey = get_active_survey(db, business_number)
    if not survey:
        return None

    if datetime.utcnow() >= survey.ends_at:
        return close_survey(db, survey, manual=False)

    return None


def record_response(
    db: Session,
    survey: Survey,
    client_number: str,
    button_id: str,
) -> bool:
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

    button_defs = SURVEY_BUTTON_SETS[survey.button_set]["buttons"]
    tag = next(b["tag"] for b in button_defs if b["id"] == button_id)

    response = SurveyResponse(
        survey_id=survey.id,
        client_number=client_number,
        button_id=button_id,
        tag=tag,
    )

    db.add(response)
    db.commit()
    return True


def build_survey_summary_text(db: Session, survey: Survey) -> str:
    responses = (
        db.query(SurveyResponse)
        .filter(SurveyResponse.survey_id == survey.id)
        .all()
    )

    button_defs = SURVEY_BUTTON_SETS[survey.button_set]["buttons"]

    counts = {b["id"]: 0 for b in button_defs}
    tags = {b["tag"]: 0 for b in button_defs}

    for r in responses:
        if r.button_id in counts:
            counts[r.button_id] += 1
        if r.tag in tags:
            tags[r.tag] += 1

    results_lines = [f"{b['text']} — {counts[b['id']]}" for b in button_defs]
    tag_lines = [f"{tag}: {count} clients" for tag, count in tags.items()]

    return ADMIN_SURVEY_SUMMARY_TEMPLATE.format(
        question=survey.question,
        total=len(responses),
        results="\n".join(results_lines),
        tags="\n".join(tag_lines),
    )
