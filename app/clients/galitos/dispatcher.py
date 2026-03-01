# ==================================================
# File: dispatcher.py
# Path: app/clients/galitos/dispatcher.py
# Project: KLResolute WhatsApp SaaS MVP
#
# Sprint 17 – Tenant Isolation Refactor (Phase 2)
#
# Purpose:
# Galitos Tenant-Specific Dispatcher
#
# Responsibilities:
# - Own all GALITOS inbound routing
# - Handle feedback
# - Delegate to existing inbound router
# - Execute enabled modules (GALITOS scope only)
# - Terminate safely (no cross-tenant fallback)
#
# Isolation:
# - No tier1 router
# - No global fallback
# - No cross-client execution
# ==================================================

from __future__ import annotations

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.clients.galitos.inbound import handle_inbound as galitos_inbound
from app.clients.galitos.feedback.handler import (
    handle_feedback_message as galitos_feedback_handler,
)
from app.modules.announcements.admin_announcements_media_handler import (
    handle_media_message as announcements_media_handler,
)
from app.clients.galitos.survey import handler as survey_handler

logger = logging.getLogger("galitos.dispatcher")


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
        "GALITOS_DISPATCH_ENTER | sender=%s | msg_type=%s",
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
                        WHERE client_code = :code
                          AND is_active = true
                        """
                    ),
                    {"code": profile.client_code},
                )
                .mappings()
                .all()
            )

            admin_numbers = {row["msisdn"] for row in admin_rows}

            handled = galitos_feedback_handler(
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

        # ---- Core Galitos Inbound (Orders + Commands) ----
        handled = galitos_inbound(
            db=db,
            business_msisdn=business_msisdn,
            sender=sender,
            msg=msg,
        )

        return True if handled else True  # Always terminate (hard isolation)

    # --------------------------------------------------
    # ANNOUNCEMENTS MODULE (GALITOS scoped)
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
    # SURVEY MODULE (GALITOS scoped)
    # --------------------------------------------------
    if "survey" in profile.enabled_modules:

        handled = survey_handler.handle(
            db=db,
            msg=msg,
            sender=sender,
            business_msisdn=business_msisdn,
        )

        if handled:
            return True

    # --------------------------------------------------
    # SAFE TERMINATION
    # --------------------------------------------------
    logger.info("GALITOS_DISPATCH_TERMINATE_SAFE")

    return True