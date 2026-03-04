# ==================================================
# File: survey_handler.py
# Path: app/clients/fatginger/survey/survey_handler.py
# Project: KLResolute WhatsApp SaaS MVP
#
# Sprint 24 – Survey Safety Enhancements
#
# Purpose:
# Handles FatGinger admin survey commands.
#
# Features:
# - Start survey (SURVEY: question)
# - Prevent multiple active surveys
# - Allow manual close (END SURVEY)
#
# Rules:
# - Case insensitive command matching
# - Only one ACTIVE survey allowed
# - No schema changes
# - No cross-tenant logic
# ==================================================

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.messaging.client_messenger import send_message

logger = logging.getLogger("fatginger.survey_handler")


ACTIVE_SURVEY_WARNING = (
    "⚠️ An active survey already exists.\n\n"
    "To close the active survey early, type:\n"
    "END SURVEY"
)


def handle_survey_command(
    *,
    db: Session,
    sender_msisdn: str,
    business_msisdn: str,
    message_text: str | None,
) -> bool:

    msg = (message_text or "").strip()
    msg_lower = msg.lower()

    # --------------------------------------------------
    # END SURVEY (manual close)
    # --------------------------------------------------
    if msg_lower == "end survey":

        result = db.execute(
            text(
                """
                SELECT id
                FROM surveys
                WHERE status = 'ACTIVE'
                LIMIT 1
                """
            )
        ).fetchone()

        if not result:
            send_message(
                db=db,
                business_msisdn=business_msisdn,
                to_number=sender_msisdn,
                text="There is no active survey.",
            )
            return True

        survey_id = result.id

        db.execute(
            text(
                """
                UPDATE surveys
                SET status = 'CLOSED',
                    closed_at = NOW()
                WHERE id = :sid
                """
            ),
            {"sid": survey_id},
        )

        db.commit()

        send_message(
            db=db,
            business_msisdn=business_msisdn,
            to_number=sender_msisdn,
            text="Survey closed.",
        )

        return True

    # --------------------------------------------------
    # START SURVEY
    # --------------------------------------------------
    if not msg_lower.startswith("survey:"):
        return False

    parts = msg.split(":", 1)
    if len(parts) < 2:
        return True

    question = parts[1].strip()

    if not question:
        send_message(
            db=db,
            business_msisdn=business_msisdn,
            to_number=sender_msisdn,
            text="Survey question cannot be empty.",
        )
        return True

    # --------------------------------------------------
    # Check existing ACTIVE survey
    # --------------------------------------------------
    active = db.execute(
        text(
            """
            SELECT id
            FROM surveys
            WHERE status = 'ACTIVE'
            LIMIT 1
            """
        )
    ).fetchone()

    if active:

        send_message(
            db=db,
            business_msisdn=business_msisdn,
            to_number=sender_msisdn,
            text=ACTIVE_SURVEY_WARNING,
        )

        return True

    # --------------------------------------------------
    # Create survey
    # --------------------------------------------------
    start_time = datetime.utcnow()
    end_time = start_time + timedelta(hours=24)

    db.execute(
        text(
            """
            INSERT INTO surveys
            (question, started_at, ends_at, status, business_number, button_set)
            VALUES (:q, :start, :end, 'ACTIVE', :bn, 'SENTIMENT')
            """
        ),
        {
            "q": question,
            "start": start_time,
            "end": end_time,
            "bn": business_msisdn,
        },
    )

    db.commit()

    send_message(
        db=db,
        business_msisdn=business_msisdn,
        to_number=sender_msisdn,
        text="Survey started successfully.",
    )

    return True