# ==================================================
# File: survey_response_handler.py
# Path: app/clients/fatginger/survey/survey_response_handler.py
# Project: KLResolute WhatsApp SaaS MVP
#
# Sprint 24 – Survey Response Capture
#
# Purpose:
# Records FatGinger survey button responses.
#
# Rules:
# - Only ACTIVE survey accepted
# - One response per message
# - No schema changes
# - Tenant isolated
# ==================================================

from __future__ import annotations

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger("fatginger.survey_response_handler")


def handle_survey_response(
    *,
    db: Session,
    sender_msisdn: str,
    business_msisdn: str,
    button_id: str | None,
    button_text: str | None,
) -> bool:

    if not button_id:
        return False

    # --------------------------------------------------
    # Find ACTIVE survey
    # --------------------------------------------------
    survey = db.execute(
        text(
            """
            SELECT id
            FROM surveys
            WHERE status = 'ACTIVE'
            AND business_number = :bn
            LIMIT 1
            """
        ),
        {"bn": business_msisdn},
    ).fetchone()

    if not survey:
        logger.info("FG_SURVEY_RESPONSE_NO_ACTIVE")
        return True

    survey_id = survey.id

    # --------------------------------------------------
    # Map button -> tag
    # --------------------------------------------------
    tag = button_id.upper()

    # --------------------------------------------------
    # Insert response
    # --------------------------------------------------
    db.execute(
        text(
            """
            INSERT INTO survey_responses
            (survey_id, client_number, button_id, tag)
            VALUES (:sid, :phone, :btn, :tag)
            """
        ),
        {
            "sid": survey_id,
            "phone": sender_msisdn,
            "btn": button_id,
            "tag": tag,
        },
    )

    db.commit()

    logger.info(
        "FG_SURVEY_RESPONSE_RECORDED | survey_id=%s | phone=%s | tag=%s",
        survey_id,
        sender_msisdn,
        tag,
    )

    return True