# ==================================================
# File: survey_handler.py
# Path: app/clients/fatginger/survey/survey_handler.py
# Project: KLResolute WhatsApp SaaS MVP
#
# Sprint 25 – Tenant Survey Isolation
#
# Purpose:
# Handles FatGinger admin survey commands.
#
# Features:
# - Start survey (SURVEY: question)
# - Prevent multiple active surveys
# - Allow manual close (END SURVEY)
# - Broadcast survey template to opted-in customers
# - Send survey results to admin when survey closes
#
# Rules:
# - Case insensitive command matching
# - Only one ACTIVE survey allowed
# - Tenant-isolated tables
# ==================================================

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.messaging.client_messenger import send_message
from app.messaging.template_registry import SURVEY_TEMPLATE_V1

logger = logging.getLogger("fatginger.survey_handler")


ACTIVE_SURVEY_WARNING = (
    "⚠️ An active survey already exists.\n\n"
    "To close it first send:\n"
    "END SURVEY"
)


def start_survey(
    *,
    db: Session,
    admin_msisdn: str,
    business_msisdn: str,
    question: str,
) -> None:

    try:

        # ----------------------------------------
        # Check for existing active survey
        # ----------------------------------------
        active = db.execute(
            text(
                """
                SELECT id
                FROM r_fg__surveys
                WHERE status = 'ACTIVE'
                LIMIT 1
                """
            )
        ).fetchone()

        if active:

            send_message(
                to=admin_msisdn,
                body=ACTIVE_SURVEY_WARNING,
                business_msisdn=business_msisdn,
            )

            return

        survey_id = str(uuid.uuid4())

        # ----------------------------------------
        # Create survey
        # ----------------------------------------
        db.execute(
            text(
                """
                INSERT INTO r_fg__surveys (
                    id,
                    question,
                    started_at,
                    ends_at,
                    status,
                    button_set
                )
                VALUES (
                    :id,
                    :question,
                    :started_at,
                    :ends_at,
                    'ACTIVE',
                    'SURVEY_TEMPLATE_V1'
                )
                """
            ),
            {
                "id": survey_id,
                "question": question,
                "started_at": datetime.utcnow(),
                "ends_at": datetime.utcnow() + timedelta(hours=24),
            },
        )

        db.commit()

        # ----------------------------------------
        # Broadcast template
        # ----------------------------------------
        customers = db.execute(
            text(
                """
                SELECT client_number
                FROM r_fg__customers
                WHERE survey_opt_in = TRUE
                """
            )
        ).fetchall()

        for row in customers:

            try:

                send_message(
                    to=row.client_number,
                    template=SURVEY_TEMPLATE_V1,
                    business_msisdn=business_msisdn,
                    variables={
                        "question": question,
                        "survey_id": survey_id,
                    },
                )

            except Exception:
                logger.exception("SURVEY_BROADCAST_FAIL")

        send_message(
            to=admin_msisdn,
            body="✅ Survey started.",
            business_msisdn=business_msisdn,
        )

    except Exception:

        logger.exception("SURVEY_START_FAIL")

        try:
            db.rollback()
        except Exception:
            pass


def end_survey(
    *,
    db: Session,
    admin_msisdn: str,
    business_msisdn: str,
) -> None:

    try:

        survey = db.execute(
            text(
                """
                SELECT id
                FROM r_fg__surveys
                WHERE status = 'ACTIVE'
                LIMIT 1
                """
            )
        ).fetchone()

        if not survey:

            send_message(
                to=admin_msisdn,
                body="No active survey.",
                business_msisdn=business_msisdn,
            )

            return

        survey_id = survey.id

        db.execute(
            text(
                """
                UPDATE r_fg__surveys
                SET status = 'CLOSED',
                    closed_at = now()
                WHERE id = :survey_id
                """
            ),
            {"survey_id": survey_id},
        )

        db.commit()

        # ----------------------------------------
        # Gather results
        # ----------------------------------------
        results = db.execute(
            text(
                """
                SELECT button_id, COUNT(*) as votes
                FROM r_fg__survey_responses
                WHERE survey_id = :survey_id
                GROUP BY button_id
                """
            ),
            {"survey_id": survey_id},
        ).fetchall()

        summary = "📊 Survey Results\n\n"

        for r in results:
            summary += f"{r.button_id}: {r.votes}\n"

        send_message(
            to=admin_msisdn,
            body=summary,
            business_msisdn=business_msisdn,
        )

    except Exception:

        logger.exception("SURVEY_END_FAIL")

        try:
            db.rollback()
        except Exception:
            pass