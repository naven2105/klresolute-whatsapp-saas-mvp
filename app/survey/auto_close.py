"""
File: app/survey/auto_close.py

Purpose:
Auto-close expired surveys AND notify admin with summary.
"""

from datetime import datetime
import logging
from sqlalchemy.orm import Session

from app.survey.survey_models import Survey
from app.survey import build_survey_summary_text
from app.outbound.factory import get_meta_client

logger = logging.getLogger(__name__)


def auto_close_expired_surveys(db: Session, business_number: str) -> int:
    """
    Close expired active surveys.
    Sends admin summary for each closed survey.
    Returns number of surveys closed.
    """
    now = datetime.utcnow()

    try:
        expired = (
            db.query(Survey)
            .filter(
                Survey.status == "active",
                Survey.ends_at <= now,
            )
            .all()
        )
    except Exception:
        logger.exception(
            "SURVEY_AUTO_CLOSE_QUERY_FAILED | business_number=%s",
            business_number,
        )
        raise

    if not expired:
        return 0

    summaries: list[str] = []
    closed_count = 0

    try:
        for survey in expired:
            survey.status = "closed"
            survey.closed_at = now
            closed_count += 1
            summaries.append(build_survey_summary_text(db, survey))

        db.commit()
    except Exception:
        logger.exception(
            "SURVEY_AUTO_CLOSE_DB_UPDATE_FAILED | business_number=%s | survey_count=%s",
            business_number,
            len(expired),
        )
        raise

    meta = get_meta_client()

    for summary in summaries:
        try:
            meta.send_generic_business_update_template(
                to_msisdn=business_number,
                blob_text=summary,
            )
        except Exception:
            logger.exception(
                "SURVEY_AUTO_CLOSE_NOTIFY_FAILED | business_number=%s",
                business_number,
            )
            raise

    return closed_count
