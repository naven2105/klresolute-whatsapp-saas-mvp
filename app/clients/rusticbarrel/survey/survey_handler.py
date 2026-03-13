from __future__ import annotations

"""
File: survey_handler.py
Path: app/clients/rusticbarrel/survey/survey_handler.py
Project: KLResolute WhatsApp SaaS MVP

Sprint 25 – Tenant Survey Isolation
"""

import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.messaging.client_messenger import send_message
from app.messaging.template_registry import SURVEY_TEMPLATE_V1
from app.clients.rusticbarrel.survey.summary import build_survey_summary_text

logger = logging.getLogger("rusticbarrel.survey_handler")


ACTIVE_SURVEY_WARNING = (
    "⚠️ An active survey already exists.\n\n"
    "To close it first send:\n"
    "END SURVEY"
)


def handle_survey_command(
    *,
    db: Session,
    sender_msisdn: str,
    business_msisdn: str,
    message_text: str,
) -> bool:

    try:

        text_clean = (message_text or "").strip()

        if text_clean.upper().startswith("SURVEY:"):

            question = text_clean.split(":", 1)[1].strip()

            active = db.execute(
                text(
                    """
                    SELECT id
                    FROM r_rusticbarrel__surveys
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

            survey_id = str(uuid.uuid4())

            db.execute(
                text(
                    """
                    INSERT INTO r_rusticbarrel__surveys (
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

            customers = db.execute(
                text(
                    """
                    SELECT phone
                    FROM r_rusticbarrel__customers
                    WHERE marketing_opt_in = TRUE
                    AND phone NOT IN (
                        SELECT msisdn
                        FROM rusticbarrel__staff
                    )
                    """
                )
            ).fetchall()

            for row in customers:

                try:

                    send_message(
                        db=db,
                        business_msisdn=business_msisdn,
                        to_number=row.phone,
                        template_name=SURVEY_TEMPLATE_V1,
                        template_params=[question],
                    )

                except Exception:
                    logger.exception("SURVEY_BROADCAST_FAIL")

            send_message(
                db=db,
                business_msisdn=business_msisdn,
                to_number=sender_msisdn,
                text="✅ Survey started.",
            )

            return True

        if text_clean.upper() == "END SURVEY":

            survey = db.execute(
                text(
                    """
                    SELECT id
                    FROM r_rusticbarrel__surveys
                    WHERE status = 'ACTIVE'
                    LIMIT 1
                    """
                )
            ).fetchone()

            if not survey:

                send_message(
                    db=db,
                    business_msisdn=business_msisdn,
                    to_number=sender_msisdn,
                    text="No active survey.",
                )

                return True

            survey_id = survey.id

            db.execute(
                text(
                    """
                    UPDATE r_rusticbarrel__surveys
                    SET status = 'CLOSED',
                        closed_at = now()
                    WHERE id = :survey_id
                    """
                ),
                {"survey_id": survey_id},
            )

            db.commit()

            question_row = db.execute(
                text(
                    """
                    SELECT question
                    FROM r_rusticbarrel__surveys
                    WHERE id = :survey_id
                    """
                ),
                {"survey_id": survey_id},
            ).fetchone()

            question = question_row.question if question_row else ""

            summary = build_survey_summary_text(
                db=db,
                survey_id=survey_id,
                question=question,
            )

            send_message(
                db=db,
                business_msisdn=business_msisdn,
                to_number=sender_msisdn,
                text=summary,
            )

            return True

        return False

    except Exception:

        logger.exception("SURVEY_COMMAND_FAIL")

        try:
            db.rollback()
        except Exception:
            pass

        return False