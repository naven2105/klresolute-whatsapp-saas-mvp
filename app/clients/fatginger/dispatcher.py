# ==================================================
# File: dispatcher.py
# Path: app/clients/fatginger/dispatcher.py
# Project: KLResolute WhatsApp SaaS MVP
#
# Sprint 17 – Tenant Isolation Refactor (Phase 1)
#
# Purpose:
# FatGinger Tenant-Specific Dispatcher
#
# Responsibilities:
# - Own all FATGINGER inbound routing
# - Handle feedback
# - Route text + image to inbound handler
# - Execute enabled modules (FG scope only)
# - Terminate safely (no cross-tenant fallback)
#
# Isolation:
# - No tier1 router
# - No cross-client execution
# ==================================================

from __future__ import annotations

import logging
from sqlalchemy.orm import Session

from app.clients.fatginger.inbound import handle_fatginger_inbound
from app.clients.fatginger.feedback.handler import (
    handle_feedback_message as fatginger_feedback_handler,
)

from app.clients.fatginger.announcements.media_handler import (
    handle_media_message as announcements_media_handler,
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
    # TEXT MESSAGES
    # --------------------------------------------------
    if msg_type == "text":

        body_text = (msg.get("text", {}) or {}).get("body", "").strip()

        # ---- Feedback ----
        if body_text.lower().startswith("feedback:"):

            handled = fatginger_feedback_handler(
                db=db,
                sender_number=sender,
                message_text=body_text,
                media_id=None,
                media_type=None,
                client_id=client_id,
                admin_numbers=set(),
                business_msisdn=business_msisdn,
            )

            if handled:
                return True

        # ---- Core Inbound ----
        handled = handle_fatginger_inbound(
            db=db,
            sender_msisdn=sender,
            business_msisdn=business_msisdn,
            message_text=body_text,
            message_type="text",
            media_url=None,
        )

        return True if handled else True  # Always terminate (hard isolation)

    # --------------------------------------------------
    # IMAGE MESSAGES
    # --------------------------------------------------
    if msg_type == "image":

        image_data = msg.get("image", {}) or {}
        media_id = image_data.get("id")
        caption = image_data.get("caption")

        handled = handle_fatginger_inbound(
            db=db,
            sender_msisdn=sender,
            business_msisdn=business_msisdn,
            message_text=caption,
            message_type="image",
            media_url=media_id,
        )

        return True if handled else True  # Always terminate

    # --------------------------------------------------
    # ANNOUNCEMENTS MODULE (FG scoped)
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


    # --------------------------------------------------
    # SAFE TERMINATION
    # --------------------------------------------------
    logger.info("FG_DISPATCH_TERMINATE_SAFE")

    return True