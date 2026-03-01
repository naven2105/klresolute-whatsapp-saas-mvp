from __future__ import annotations

"""
File: app/modules/survey/service.py
Path: app/modules/survey/service.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Survey service compatibility wrapper.

This file exists to provide a stable import surface for the Survey module.
It delegates all real logic to lifecycle.py while enforcing guard rails.

LOCKED RULES:
- No messaging
- No Meta / outbound calls
- No DB schema decisions
- Must never raise exceptions
- Must return safe defaults on failure

This file MUST remain thin.
"""

import logging
from sqlalchemy.orm import Session

from app.clients.galitos.survey.models import Survey
from app.clients.galitos.survey.lifecycle import (
    get_active_survey as _get_active_survey,
    record_response as _record_response,
)

logger = logging.getLogger("module.survey.service")


def get_active_survey(db: Session, business_msisdn: str) -> Survey | None:
    """
    Return the currently active survey for a business, if any.
    Never raises.
    """
    try:
        return _get_active_survey(db, business_msisdn)
    except Exception as exc:
        logger.exception(
            "SURVEY_SERVICE_GET_ACTIVE_FAILED | business=%s | err=%s",
            business_msisdn,
            exc,
        )
        return None


def record_response(
    *,
    db: Session,
    survey: Survey,
    client_number: str,
    button_id: str,
) -> bool:
    """
    Record a survey response.
    Returns True if recorded, False otherwise.
    Never raises.
    """
    try:
        return _record_response(
            db=db,
            survey=survey,
            client_number=client_number,
            button_id=button_id,
        )
    except Exception as exc:
        logger.exception(
            "SURVEY_SERVICE_RECORD_RESPONSE_FAILED | survey_id=%s | client=%s | button=%s | err=%s",
            getattr(survey, "id", None),
            client_number,
            button_id,
            exc,
        )
        return False
