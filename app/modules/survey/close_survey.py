from __future__ import annotations

"""
File: app/modules/survey/close_survey.py
Path: app/modules/survey/close_survey.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Single authoritative way to close a survey
and notify admin exactly once.
"""

from datetime import datetime
from sqlalchemy.orm import Session

# ---- Survey module import (FIXED) ----
from app.modules.survey.survey_models import Survey
from app.modules.survey.summary import build_survey_summary_text
from app.outbound.factory import get_meta_client


def close_survey_and_notify(
    *,
    db: Session,
    survey: Survey,
    closed_by: str,  # "auto" | "admin"
) -> None:
    """
    Close survey and send admin summary exactly once.
    """

    if survey.status != "active":
        return  # idempotent safety

    now = datetime.utcnow()

    survey.status = "closed"
    survey.closed_at = now
    db.commit()

    meta = get_meta_client()

    summary = build_survey_summary_text(
        db=db,
        survey=survey,
        closed_by=closed_by,
    )

    meta.send_generic_business_update_template(
        to_msisdn=survey.business_number,
        blob_text=summary,
    )
