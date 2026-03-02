# ==================================================
# File: dispatcher.py
# Path: app/clients/magen/dispatcher.py
# Project: KLResolute WhatsApp SaaS MVP
#
# Sprint 20 – UUID Identity Alignment
#
# Purpose:
# Magen Tenant-Specific Dispatcher
#
# Isolation:
# - UUID-only identity
# - No client_code usage
# ==================================================

from __future__ import annotations

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.clients.magen.inbound import handle_inbound as magen_inbound
from app.clients.magen.feedback.handler import (
    handle_feedback_message as magen_feedback_handler,
)


from app.clients.magen.announcements.media_handler import (
    handle_media_message as announcements_media_handler,
)


logger = logging.getLogger("magen.dispatcher")


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
        "MAGEN_DISPATCH_ENTER | sender=%s | msg_type=%s",
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

            admin_rows = (
                db.execute(
                    text(
                        """
                        SELECT msisdn
                        FROM client_admins
                        WHERE client_id = :client_id
                          AND is_active = TRUE
                        """
                    ),
                    {"client_id": client_id},
                )
                .mappings()
                .all()
            )

            admin_numbers = {row["msisdn"] for row in admin_rows}

            handled = magen_feedback_handler(
                db=db,
                sender_number=sender,
                message_text=body_text,
                media_id=None,
                media_type=None,
                client_id=client_id,
                admin_numbers=admin_numbers,
                business_msisdn=business_msisdn,
            )

            if handled:
                return True

        # ---- Core Magen Inbound ----
        handled = magen_inbound(
            db=db,
            msg=msg,
            sender=sender,
            business_msisdn=business_msisdn,
        )

        return True  # Hard isolation

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

    logger.info("MAGEN_DISPATCH_TERMINATE_SAFE")

    return True