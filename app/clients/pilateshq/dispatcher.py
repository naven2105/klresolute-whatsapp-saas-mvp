# ==================================================
# File: dispatcher.py
# Path: app/clients/pilateshq/dispatcher.py
# Project: KLResolute WhatsApp SaaS MVP
#
# Sprint 17 – Tenant Isolation Refactor (Phase 4)
#
# Purpose:
# PilatesHQ Tenant-Specific Dispatcher
#
# Responsibilities:
# - Own all PILATESHQ inbound routing
# - Handle feedback
# - Delegate to existing inbound router
# - Execute enabled modules (PILATESHQ scope only)
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

from app.clients.pilateshq.inbound import handle_inbound as pilates_inbound
from app.clients.pilateshq.feedback.handler import (
    handle_feedback_message as pilates_feedback_handler,
)
from app.modules.announcements.admin_announcements_media_handler import (
    handle_media_message as announcements_media_handler,
)

logger = logging.getLogger("pilateshq.dispatcher")


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
        "PILATESHQ_DISPATCH_ENTER | sender=%s | msg_type=%s",
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

            handled = pilates_feedback_handler(
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

        # ---- Core Pilates Inbound ----
        handled = pilates_inbound(
            db=db,
            sender=sender,
            msg=msg,
            business_msisdn=business_msisdn,
        )

        return True if handled else True  # Always terminate

    # --------------------------------------------------
    # ANNOUNCEMENTS MODULE (PILATESHQ scoped)
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
    logger.info("PILATESHQ_DISPATCH_TERMINATE_SAFE")

    return True