"""
File: app/survey/auto_close.py

Purpose:
Auto-close expired surveys AND notify admin with summary.
"""

from datetime import datetime
from sqlalchemy.orm import Session

from app.survey.survey_models import Survey
from app.survey import build_survey_summary_text
from app.outbound.factory import get_meta_client


def auto_close_expired_surveys(db: Session, business_number: str) -> int:
    """
    Close expired active surveys.
    Sends admin summary for each closed survey.
    Returns number of surveys closed.
    """
    now = datetime.utcnow()

    expired = (
        db.query(Survey)
        .filter(
            Survey.status == "active",
            Survey.ends_at <= now,
        )
        .all()
    )

    if not expired:
        return 0

    meta = get_meta_client()
    closed_count = 0

    for survey in expired:
        survey.status = "closed"
        survey.closed_at = now
        closed_count += 1

        # ✅ Send same summary as manual close
        meta.send_generic_business_update_template(
            to_msisdn=business_number,
            blob_text=build_survey_summary_text(db, survey),
        )

    db.commit()
    return closed_count
