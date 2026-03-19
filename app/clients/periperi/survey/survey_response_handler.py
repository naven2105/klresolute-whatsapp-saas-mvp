# ==================================================
# File: survey_response_handler.py
# Path: app/clients/periperi/survey/survey_response_handler.py
# Project: KLResolute WhatsApp SaaS MVP
#
# Sprint 25 – Tenant Survey Isolation
#
# Purpose:
# Handles incoming survey button responses from customers.
#
# Rules:
# - Tenant isolated tables
# - Never raise exceptions
# - Never break dispatcher
# ==================================================

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger("periperi.survey_response_handler")


def handle_survey_response(
    *,
    db: Session,
    client_number: str,
    button_id: str,
    tag: str | None = None,
) -> None:

    try:

        survey = db.execute(
            text(
                """
                SELECT id
                FROM r_periperi__surveys
                WHERE status = 'ACTIVE'
                LIMIT 1
                """
            )
        ).fetchone()

        if not survey:
            return

        survey_id = survey.id

        db.execute(
            text(
                """
                INSERT INTO r_periperi__survey_responses (
                    id,
                    survey_id,
                    client_number,
                    button_id,
                    tag,
                    created_at
                )
                VALUES (
                    :id,
                    :survey_id,
                    :client_number,
                    :button_id,
                    :tag,
                    :created_at
                )
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "survey_id": survey_id,
                "client_number": client_number,
                "button_id": button_id,
                "tag": tag,
                "created_at": datetime.utcnow(),
            },
        )

        db.commit()

    except Exception:

        logger.exception("SURVEY_RESPONSE_SAVE_FAIL")

        try:
            db.rollback()
        except Exception:
            pass
