from __future__ import annotations

"""
File: app/modules/survey/service.py
Path: app/modules/survey/service.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Compatibility wrapper for module imports.

Rules:
- No messaging
- No Meta
- Delegates to lifecycle.py
"""

from sqlalchemy.orm import Session

from app.modules.survey.models import Survey
from app.modules.survey.lifecycle import (
    get_active_survey as _get_active_survey,
    record_response as _record_response,
)


def get_active_survey(db: Session, business_msisdn: str) -> Survey | None:
    return _get_active_survey(db, business_msisdn)


def record_response(
    *,
    db: Session,
    survey: Survey,
    client_number: str,
    button_id: str,
) -> bool:
    return _record_response(
        db=db,
        survey=survey,
        client_number=client_number,
        button_id=button_id,
    )
