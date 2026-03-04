from __future__ import annotations

"""
File: survey_handler.py
Path: app/clients/fatginger/survey/survey_handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Admin survey command handler.

Command:
survey: <question>
"""

import logging
from sqlalchemy.orm import Session

from app.messaging.client_messenger import send_message
from app.clients.fatginger.survey.survey_service import send_survey

logger = logging.getLogger("fatginger.survey_handler")


def handle_survey_command(
    *,
    db: Session,
    sender_msisdn: str,
    business_msisdn: str,
    message_text: str,
) -> bool:

    msg = (message_text or "").strip()

    if not msg.lower().startswith("survey:"):
        return False

    question = msg.split("survey:", 1)[1].strip()

    if not question:
        send_message(
            db=db,
            business_msisdn=business_msisdn,
            to_number=sender_msisdn,
            text="Please provide a survey question.\nExample:\nsurvey: How was your meal today?",
        )
        return True

    send_survey(
        db=db,
        business_msisdn=business_msisdn,
        question=question,
    )

    send_message(
        db=db,
        business_msisdn=business_msisdn,
        to_number=sender_msisdn,
        text="Survey sent to customers.",
    )

    return True