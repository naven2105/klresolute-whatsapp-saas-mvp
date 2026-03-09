# ==================================================
# File: dispatcher.py
# Path: app/clients/zar/dispatcher.py
# Project: KLResolute WhatsApp SaaS MVP
#
# Update:
# - Deep execution logging for full flow visibility
# - No logic changes
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

    msg_type = msg.get("type")

    logger.info(
        "ZAR_FLOW_START | sender=%s | business=%s | msg_type=%s",
        sender,
        business_msisdn,
        msg_type,
    )

    logger.info(
        "ZAR_MSG_PAYLOAD | sender=%s | payload=%s",
        sender,
        msg,
    )

    # --------------------------------------------------
    # BUTTON MESSAGES
    # --------------------------------------------------
    if msg_type == "button":

        logger.info("ZAR_FLOW_BRANCH | BUTTON_HANDLER")

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

        logger.info("ZAR_FLOW_END | BUTTON_HANDLED")

        return True

    # --------------------------------------------------
    # TEXT MESSAGES
    # --------------------------------------------------
    if msg_type == "text":

        logger.info("ZAR_FLOW_BRANCH | TEXT_HANDLER")

        body_text = (msg.get("text", {}) or {}).get("body", "").strip()

        logger.info(
            "ZAR_TEXT_BODY | sender=%s | text=%r",
            sender,
            body_text,
        )

        handled = handle_menu_confirmation(
            db=db,
            sender_msisdn=sender,
            business_msisdn=business_msisdn,
            message_text=body_text,
        )

        logger.info(
            "ZAR_MENU_CONFIRM_CHECK | result=%s",
            handled,
        )

        if handled:
            logger.info("ZAR_FLOW_END | MENU_CONFIRMATION_HANDLED")
            return True

        if body_text.lower().startswith("feedback:"):

            logger.info("ZAR_FLOW_BRANCH | FEEDBACK_HANDLER")

            handled = zar_feedback_handler(
                db=db,
                sender_number=sender,
                message_text=body_text,
                media_id=None,
                media_type=None,
                business_msisdn=business_msisdn,
            )

            logger.info("ZAR_FEEDBACK_RESULT | handled=%s", handled)

            if handled:
                logger.info("ZAR_FLOW_END | FEEDBACK_HANDLED")
                return True

        logger.info("ZAR_FLOW_BRANCH | INBOUND_TEXT_ROUTING")

        handled = handle_zar_inbound(
            db=db,
            sender_msisdn=sender,
            business_msisdn=business_msisdn,
            message_text=body_text,
            message_type="text",
            media_url=None,
        )

        logger.info("ZAR_INBOUND_TEXT_RESULT | handled=%s", handled)

        return handled

    # --------------------------------------------------
    # IMAGE MESSAGES
    # --------------------------------------------------
    if msg_type == "image":

        logger.info("ZAR_FLOW_BRANCH | IMAGE_HANDLER")

        image_data = msg.get("image", {}) or {}
        media_id = image_data.get("id")

        caption_raw = image_data.get("caption") or ""
        caption = caption_raw.strip()
        caption_lower = caption.lower()

        logger.info(
            "ZAR_IMAGE_DETAILS | sender=%s | media_id=%s | caption_raw=%r | caption_stripped=%r",
            sender,
            media_id,
            caption_raw,
            caption,
        )

        admin_match = is_admin_message(
            db=db,
            sender=sender,
            business_msisdn=business_msisdn,
        )

        logger.info(
            "ZAR_ADMIN_CHECK | sender=%s | is_admin=%s",
            sender,
            admin_match,
        )

        if admin_match and caption_lower in {"food", "food menu"}:

            logger.info(
                "ZAR_FLOW_BRANCH | FOOD_MENU_INTERCEPT | media_id=%s",
                media_id,
            )

            return store_menu_image(
                db=db,
                sender_msisdn=sender,
                business_msisdn=business_msisdn,
                media_id=media_id,
            )

        logger.info("ZAR_FLOW_BRANCH | IMAGE_INBOUND_ROUTING")

        handled = handle_zar_inbound(
            db=db,
            sender_msisdn=sender,
            business_msisdn=business_msisdn,
            message_text=caption,
            message_type="image",
            media_url=media_id,
        )

        logger.info("ZAR_IMAGE_INBOUND_RESULT | handled=%s", handled)

        return handled

    # --------------------------------------------------
    # ANNOUNCEMENTS MODULE
    # --------------------------------------------------
    logger.info("ZAR_FLOW_BRANCH | ANNOUNCEMENTS_CHECK")

    if "announcements" in profile.enabled_modules:

        handled = announcements_media_handler(
            db=db,
            sender=sender,
            msg=msg,
            client_id=client_id,
            business_msisdn=business_msisdn,
        )

        logger.info("ZAR_ANNOUNCEMENT_RESULT | handled=%s", handled)

        if handled:
            logger.info("ZAR_FLOW_END | ANNOUNCEMENT_HANDLED")
            return True

    logger.info("ZAR_FLOW_END | SAFE_EXIT")

    return True