from __future__ import annotations

"""
File: app/modules/survey/auto_close.py
Path: app/modules/survey/auto_close.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Background expiry worker.

Responsibilities (LOCKED):
- Auto-close expired surveys
- Auto-close expired Magen inspections
- No messaging
- No PDF generation logic here
"""

import logging
from sqlalchemy.orm import Session

# ---- Survey module imports (UPDATED) ----
from app.clients.galitos.survey.service import (
    get_expired_active_surveys,
    close_survey,
)

# ---- Cross-module dependency (unchanged, intentional) ----
from app.clients.magen.inspection.auto_close_worker import auto_close_expired_inspections

logger = logging.getLogger("survey_expiry_notifier")

def auto_close_expired_surveys(db: Session, business_number: str | None = None):
    """
    Runs periodically by background scheduler.
    """

    try:
        # ----------------------------------
        # Survey expiry
        # ----------------------------------
        expired = get_expired_active_surveys(db, business_number)

        for survey in expired:
            close_survey(db, survey)

        if expired:
            logger.info(
                "SURVEY_EXPIRY | closed=%s",
                len(expired),
            )

    except Exception:
        logger.exception("SURVEY_EXPIRY_FATAL")

    # ----------------------------------
    # Magen inspection auto-close
    # ----------------------------------
    try:
        closed = auto_close_expired_inspections(db)

        if closed:
            logger.info(
                "MAGEN_EXPIRY | auto_closed=%s",
                closed,
            )

    except Exception:
        logger.exception("MAGEN_EXPIRY_FATAL")
