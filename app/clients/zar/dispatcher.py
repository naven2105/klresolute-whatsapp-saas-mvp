# ==================================================
# File: dispatcher.py
# Path: app/clients/zar/dispatcher.py
# Project: KLResolute WhatsApp SaaS MVP
#
# Update:
# - Admin food menu image intercept
# - Image with caption "food" or "food menu" stores menu image
# - Prevents campaign handler from capturing the image
# - Admin YES/NO confirmation support for menu update
# - No existing logic removed
# ==================================================

from __future__ import annotations

import logging
from sqlalchemy.orm import Session

from app.utils.admin import is_admin_message
from app.clients.zar.inbound import handle_zar_inbound
from app.clients.zar.feedback.handler import (
    handle_feedback_message as zar_feedback_handler,
)
from app.clients.zar.announcements.media_handler import (
    handle_media_message as announcements_media_handler,
)

from app.clients.zar.customer.menu_service import (
    store_menu_image,
    handle_menu_confirmation,
)

logger = logging.getLogger("zar.dispatcher")


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
        "ZAR_DISPATCH_ENTER | sender=%s | msg_type=%s",
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

        from app.clients.zar.survey.survey_response_handler import (
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

        # ---- MENU UPDATE CONFIRMATION ----
        handled = handle_menu_confirmation(
            db=db,
            sender_msisdn=sender,
            business_msisdn=business_msisdn,
            message_text=body_text,
        )

        if handled:
            return True

        # ---- Feedback ----
        if body_text.lower().startswith("feedback:"):

            handled = zar_feedback_handler(
                db=db,
                sender_number=sender,
                message_text=body_text,
                media_id=None,
                media_type=None,
                business_msisdn=business_msisdn,
            )

            if handled:
                return True

        # ---- Core inbound routing ----
        handled = handle_zar_inbound(
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
        caption = (image_data.get("caption") or "").strip()

        # ---- FOOD MENU UPDATE (ADMIN ONLY) ----
        if is_admin_message(
            db=db,
            sender=sender,
            business_msisdn=business_msisdn,
        ) and caption.lower() in {"food", "food menu"}:

            return store_menu_image(
                db=db,
                sender_msisdn=sender,
                business_msisdn=business_msisdn,
                media_id=media_id,
            )

        # ---- Existing inbound flow ----
        handled = handle_zar_inbound(
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

    logger.info("ZAR_DISPATCH_TERMINATE_SAFE")

    return True