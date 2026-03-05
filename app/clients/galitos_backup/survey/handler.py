from __future__ import annotations

"""
File: app/clients/galitos/survey/handler.py
Project: KLResolute WhatsApp SaaS MVP

MVP Survey Simplification:
- Single survey type
- 3 fixed options: Positive / Neutral / Negative
- Template-based quick reply responses
"""

import logging
from sqlalchemy.orm import Session

from app.messaging.client_messenger import send_message
from app.profiles.client_profile import get_client_profile
from app.clients.galitos.survey.service import (
    get_active_survey,
    record_response,
)
from app.clients.galitos.survey.constants import CUSTOMER_SURVEY_THANK_YOU_TEMPLATE
from app.utils.admin import is_admin_message

logger = logging.getLogger("module.survey")


VALID_RESPONSES = {
    "POSITIVE": "POSITIVE",
    "NEUTRAL": "NEUTRAL",
    "NEGATIVE": "NEGATIVE",
}


def handle(
    *,
    db: Session,
    msg: dict,
    sender: str,
    business_msisdn: str,
) -> bool:

    profile = get_client_profile(
        business_msisdn,
        db=db,
    )

    if not profile:
        return False

    if "survey" not in profile.enabled_modules:
        return False

    msg_type = msg.get("type")

    button_text = None

    # ----------------------------------------------
    # INTERACTIVE (legacy interactive buttons)
    # ----------------------------------------------
    if msg_type == "interactive":
        reply = msg.get("interactive", {}).get("button_reply")
        if reply:
            button_text = (reply.get("title") or "").strip().upper()

    # ----------------------------------------------
    # TEMPLATE QUICK REPLY BUTTON (type=button)
    # ----------------------------------------------
    elif msg_type == "button":
        button_text = (msg.get("button", {}).get("text") or "").strip().upper()

    if button_text:
        if button_text not in VALID_RESPONSES:
            return False

        survey = get_active_survey(db, business_msisdn)
        if not survey:
            return True

        recorded = record_response(
            db=db,
            survey=survey,
            client_number=sender,
            button_id=button_text,
        )

        if recorded:
            send_message(
                db=db,
                business_msisdn=business_msisdn,
                to_number=sender,
                text=CUSTOMER_SURVEY_THANK_YOU_TEMPLATE,
            )

        return True

    # ----------------------------------------------
    # Ignore admin text here
    # ----------------------------------------------
    if msg_type == "text":
        if is_admin_message(
            db=db,
            sender=sender,
            business_msisdn=business_msisdn,
        ):
            return False

    return False
