# ==================================================
# File: dispatcher.py
# Path: app/clients/rusticbarrel/dispatcher.py
# Project: KLResolute WhatsApp SaaS MVP
#
# Sprint 34 – rusticbarrel Template Alignment
#
# Fix:
# - Ensure admin image "food" intercept runs before announcements module
# - Prevent announcements module from capturing menu image updates
#
# Rules:
# - No logic removed
# - No refactors
# - Minimal patch
# ==================================================

from __future__ import annotations

import logging
from sqlalchemy.orm import Session

from app.clients.rusticbarrel.inbound import handle_rusticbarrel_inbound
from app.clients.rusticbarrel.feedback.handler import (
    handle_feedback_message as rusticbarrel_feedback_handler,
)
from app.clients.rusticbarrel.announcements.media_handler import (
    handle_media_message as announcements_media_handler,
)

logger = logging.getLogger("rusticbarrel.dispatcher")


def dispatch(
    *,
    db: Session,
    msg: dict,
    sender: str,
    business_msisdn: str,
    profile,
    client_id: str,
) -> bool:

    logger.info(
        "RUSTICBARREL_DISPATCH_ENTER | sender=%s | msg_type=%s",
        sender,
        msg.get("type"),
    )

    msg_type = msg.get("type")

    # --------------------------------------------------
    # BUTTON MESSAGES (Survey responses)
    # --------------------------------------------------
    if msg_type == "button":

        button_data = msg.get("button", {}) or {}
        button_text = button_data.get("text")
        button_payload = button_data.get("payload")

        from app.clients.rusticbarrel.survey.survey_response_handler import (
            handle_survey_response,
        )

        handle_survey_response(
            db=db,
            client_number=sender,
            button_id=button_payload,
            tag=button_text,
        )

        return True

    # --------------------------------------------------
    # TEXT MESSAGES
    # --------------------------------------------------
    if msg_type == "text":

        body_text = (msg.get("text", {}) or {}).get("body", "").strip()

        # ---- Feedback ----
        if body_text.lower().startswith("feedback:"):

            handled = rusticbarrel_feedback_handler(
                db=db,
                sender_number=sender,
                message_text=body_text,
                media_id=None,
                media_type=None,
                business_msisdn=business_msisdn,
            )

            if handled:
                return True

        # ---- Core Inbound ----
        handled = handle_rusticbarrel_inbound(
            db=db,
            sender_msisdn=sender,
            business_msisdn=business_msisdn,
            message_text=body_text,
            message_type="text",
            media_url=None,
        )

        return handled

    # --------------------------------------------------
    # IMAGE MESSAGES
    # --------------------------------------------------
    if msg_type == "image":

        image_data = msg.get("image", {}) or {}
        media_id = image_data.get("id")
        caption = image_data.get("caption")

        # ---- First allow inbound to intercept admin food menu ----
        handled = handle_rusticbarrel_inbound(
            db=db,
            sender_msisdn=sender,
            business_msisdn=business_msisdn,
            message_text=caption,
            message_type="image",
            media_url=media_id,
        )

        if handled:
            return True

        # ---- If not handled, pass to announcements ----
        if "announcements" in profile.enabled_modules:

            handled = announcements_media_handler(
                db=db,
                sender=sender,
                msg=msg,
                client_id=client_id,
                business_msisdn=business_msisdn,
            )

            if handled:
                return True

    logger.info("RUSTICBARREL_DISPATCH_TERMINATE_SAFE")

    return True