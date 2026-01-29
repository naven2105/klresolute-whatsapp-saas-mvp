from __future__ import annotations

"""
File: app/modules/survey/service.py
Path: app/modules/survey/service.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Survey module service layer (module-scoped).

Responsibilities (LOCKED):
- Query active survey
- Record survey responses
- Delegate persistence to existing survey tables
- NO messaging
- NO admin logic
- NO schema definitions

This file is a thin compatibility layer while Survey is migrated
from app/survey → app/modules/survey.
"""

from sqlalchemy.orm import Session

# ---- survey models (authoritative DB schema) ----
from app.modules.survey.models import Survey, SurveyResponse

# ---- Legacy constants (authoritative definitions) ----
from app.survey.survey_constants import SURVEY_BUTTON_SETS



# -------------------------------------------------
# Active survey
# -------------------------------------------------

def get_active_survey(
    db: Session,
    business_msisdn: str,
) -> Survey | None:
    """
    Return the active survey for a business, if any.
    """
    return (
        db.query(Survey)
        .filter(
            Survey.business_number == business_msisdn,
            Survey.status == "ACTIVE",
        )
        .one_or_none()
    )


# -------------------------------------------------
# Record response
# -------------------------------------------------

def record_response(
    *,
    db: Session,
    survey: Survey,
    client_number: str,
    button_id: str,
) -> bool:
    """
    Record a survey response.

    Returns:
        True  -> response recorded
        False -> duplicate response
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

    button_defs = SURVEY_BUTTON_SETS[survey.button_set]["buttons"]
    tag = next(
        b["tag"] for b in button_defs if b["id"] == button_id
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
