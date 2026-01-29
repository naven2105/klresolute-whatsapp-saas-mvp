from __future__ import annotations

"""
File: app/modules/survey/handler.py
Path: app/modules/survey/handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Inbound entry point for Survey module.

Responsibilities (LOCKED):
- Decide if inbound message is survey-related
- Route admin survey commands
- Route customer survey responses
- Delegate all logic to survey services / handlers
- Return True if message was handled

NO database schema logic here.
NO Meta client creation here.
"""

import logging
from sqlalchemy.orm import Session

from app.handlers.admin_surveys import handle_admin_surveys

# ✅ FIXED IMPORT (actual location)
from app.handlers.client_commands import is_admin_message

# ---- Survey services (MODULE-LEVEL) ----
from app.modules.survey.service import (
    get_active_survey,
    record_response,
)

from app.modules.survey.constants import CUSTOMER_SURVEY_THANK_YOU_TEMPLATE
from app.messaging.client_messenger import send_message

from app.profiles.client_profile import get_client_profile

logger = logging.getLogger("module.survey")


def handle(
    *,
    db: Session,
    msg: dict,
    sender: str,
    business_msisdn: str,
) -> bool:
    """
    Entry point for Survey module.
    """

    profile = get_client_profile(business_msisdn)
    if not profile or "survey" not in profile.enabled_modules:
        return False

    admin_allowlist = set(profile.admin_numbers)
    msg_type = msg.get("type")

    # ----------------------------------
    # ADMIN COMMANDS
    # ----------------------------------
    if msg_type == "text":
        body = msg.get("text", {}).get("body", "").strip()
        if not body:
            return False

        if is_admin_message(sender, admin_allowlist):
            handled = handle_admin_surveys(
                db=db,
                sender_number=sender,
                message_text=body,
                admin_allowlist=admin_allowlist,
            )
            return handled

    # ----------------------------------
    # CUSTOMER SURVEY RESPONSE
    # ----------------------------------
    if msg_type == "interactive":
        reply = msg.get("interactive", {}).get("button_reply")
        if not reply:
            return False

        button_id = reply.get("id")
        if not button_id:
            return False

        survey = get_active_survey(db, business_msisdn)
        if not survey:
            logger.info(
                "SURVEY_RESPONSE_IGNORED | no active survey | sender=%s",
                sender,
            )
            return True

        recorded = record_response(
            db=db,
            survey=survey,
            client_number=sender,
            button_id=button_id,
        )

        if recorded:
            send_message(
                to_number=sender,
                text=CUSTOMER_SURVEY_THANK_YOU_TEMPLATE,
            )
            logger.info(
                "SURVEY_RESPONSE_RECORDED | survey_id=%s | sender=%s | button=%s",
                survey.id,
                sender,
                button_id,
            )
        else:
            logger.info(
                "SURVEY_RESPONSE_DUPLICATE | survey_id=%s | sender=%s",
                survey.id,
                sender,
            )

        return True

    return False
