# ==================================================
# File: dispatcher.py
# Path: app/clients/fatginger/dispatcher.py
# Project: KLResolute WhatsApp SaaS MVP
#
# Patch:
# - Add menu confirmation handling
# - Add admin food image intercept (same pattern as ZAR) 
# ==================================================

from __future__ import annotations

import logging
from sqlalchemy.orm import Session

from app.utils.admin import is_admin_message

from app.clients.fatginger.inbound import handle_fatginger_inbound
from app.clients.fatginger.feedback.handler import (
    handle_feedback_message as fatginger_feedback_handler,
)
from app.clients.fatginger.announcements.media_handler import (
    handle_media_message as announcements_media_handler,
)

from app.clients.fatginger.customer.menu_service import (
    handle_menu_confirmation,
    store_menu_image,
)

logger = logging.getLogger("fatginger.dispatcher")


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
        "FG_DISPATCH_ENTER | sender=%s | msg_type=%s",
        sender,
        msg.get("type"),
    )

    msg_type = msg.get("type")

    # --------------------------------------------------
    # BUTTON MESSAGES
    # --------------------------------------------------
    if msg_type == "button":

        button_data = msg.get("button", {}) or {}
        button_text = button_data.get("text")
        button_payload = button_data.get("payload")

        from app.clients.fatginger.survey.survey_response_handler import (
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

        # Menu confirmation
        handled = handle_menu_confirmation(
            db=db,
            sender_msisdn=sender,
            business_msisdn=business_msisdn,
            message_text=body_text,
        )

        if handled:
            return True

        # Feedback
        if body_text.lower().startswith("feedback:"):

            handled = fatginger_feedback_handler(
                db=db,
                sender_number=sender,
                message_text=body_text,
                media_id=None,
                media_type=None,
                business_msisdn=business_msisdn,
            )

            if handled:
                return True

        handled = handle_fatginger_inbound(
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

        caption_raw = image_data.get("caption") or ""
        caption = caption_raw.strip()
        caption_lower = caption.lower()

        admin_match = is_admin_message(
            db=db,
            sender=sender,
            business_msisdn=business_msisdn,
        )

        # FOOD MENU IMAGE INTERCEPT
        if admin_match and caption_lower in {"food", "food menu"}:

            return store_menu_image(
                db=db,
                sender_msisdn=sender,
                business_msisdn=business_msisdn,
                media_id=media_id,
            )

        handled = handle_fatginger_inbound(
            db=db,
            sender_msisdn=sender,
            business_msisdn=business_msisdn,
            message_text=caption,
            message_type="image",
            media_url=media_id,
        )

        return handled

    # --------------------------------------------------
    # ANNOUNCEMENTS MODULE
    # --------------------------------------------------
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

    logger.info("FG_DISPATCH_TERMINATE_SAFE")

    return True