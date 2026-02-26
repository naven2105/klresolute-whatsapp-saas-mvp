from __future__ import annotations

"""
File: app/modules/survey/close_survey.py
Path: app/modules/survey/close_survey.py
Project: KLResolute WhatsApp SaaS MVP

Sprint: Full UUID Identity Migration

Purpose:
Single authoritative way to close a survey
and notify admin exactly once.

Changes:
- Business-scoped Meta client
- Defensive rollback protection
- No global sender identity usage
"""

from datetime import datetime
from sqlalchemy.orm import Session
import logging

from app.modules.survey.survey_models import Survey
from app.modules.survey.summary import build_survey_summary_text
from app.outbound.factory import get_meta_client
from app.messaging.template_registry import FG_CAMPAIGN_TEMPLATE

logger = logging.getLogger("survey.close")


def close_survey_and_notify(
    *,
    db: Session,
    survey: Survey,
    closed_by: str,  # "auto" | "admin"
) -> None:
    """
    Close survey and send admin summary exactly once.
    """

    try:
        if survey.status != "active":
            return

        now = datetime.utcnow()

        survey.status = "closed"
        survey.closed_at = now
        db.commit()

        business_msisdn = survey.business_number

        if not business_msisdn:
            logger.error(
                "SURVEY_CLOSE_ABORT | reason=missing_business_number | survey_id=%s",
                survey.id,
            )
            return

        meta = get_meta_client(
            db=db,
            business_msisdn=business_msisdn,
        )

        summary = build_survey_summary_text(
            db=db,
            survey=survey,
            closed_by=closed_by,
        )

        meta.send_template(
            to_msisdn=business_msisdn,
            template_name=FG_CAMPAIGN_TEMPLATE,
            body_params=[summary],
        )

        logger.info(
            "SURVEY_CLOSED_AND_NOTIFIED | survey_id=%s | business=%s",
            survey.id,
            business_msisdn,
        )

    except Exception:
        db.rollback()
        logger.exception(
            "SURVEY_CLOSE_FATAL | survey_id=%s",
            getattr(survey, "id", None),
        )