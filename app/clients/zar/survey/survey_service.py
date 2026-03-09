from __future__ import annotations

"""
File: survey_service.py
Path: app/clients/zar/survey/survey_service.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
ZAR survey sending service.
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.messaging.client_messenger import send_message
from app.messaging.template_registry import SURVEY_TEMPLATE_V1

logger = logging.getLogger("zar.survey_service")


def send_survey(
    *,
    db: Session,
    business_msisdn: str,
    question: str,
):

    rows = db.execute(
        text(
            """
            SELECT phone
            FROM r_zar__customers
            WHERE marketing_opt_in = TRUE
            """
        )
    ).fetchall()

    for r in rows:

        try:

            send_message(
                db=db,
                business_msisdn=business_msisdn,
                to_number=r.phone,
                template_name=SURVEY_TEMPLATE_V1,
                template_params=[question],
            )

        except Exception:

            logger.exception(
                "ZAR_SURVEY_SEND_FAIL | phone=%s",
                r.phone,
            )