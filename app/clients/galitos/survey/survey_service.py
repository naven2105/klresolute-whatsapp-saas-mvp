from __future__ import annotations

"""
File: survey_service.py
Path: app/clients/fatginger/survey/survey_service.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
FatGinger survey sending service.

Rules:
- Tenant-isolated
- Sends survey template to opted-in customers
- Excludes staff/admin numbers defensively
- No dispatcher logic
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.messaging.client_messenger import send_message
from app.messaging.template_registry import SURVEY_TEMPLATE_V1

logger = logging.getLogger("fatginger.survey_service")


def send_survey(
    *,
    db: Session,
    business_msisdn: str,
    question: str,
) -> None:
    """
    Sends survey template to all marketing_opt_in customers.
    Staff/admin numbers are excluded defensively.
    """

    rows = db.execute(
        text(
            """
            SELECT phone
            FROM r_fg__customers
            WHERE marketing_opt_in = TRUE
            AND phone NOT IN (
                SELECT msisdn
                FROM r_galitos__staff
                WHERE role = 'admin'
            )
            """
        )
    ).fetchall()

    for row in rows:
        try:
            send_message(
                db=db,
                business_msisdn=business_msisdn,
                to_number=row.phone,
                template_name=SURVEY_TEMPLATE_V1,
                template_params=[question],
            )
        except Exception:
            logger.exception(
                "FG_SURVEY_SEND_FAIL | phone=%s",
                getattr(row, "phone", None),
            )