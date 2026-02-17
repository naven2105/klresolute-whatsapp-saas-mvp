from __future__ import annotations

"""
File: app/inbound_dispatcher.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Central inbound routing entry point.

LOCKED:
- No business logic
- No module rewrites
- Only routing + logging
- Guard rails for visibility
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.profiles.client_profile import get_client_profile
from app.handlers.tier1_router import handle_client_command as tier1_handle
from app.handlers.feedback_handler import handle_feedback_message
from app.handlers import galitos_order_handler

# ✅ Client-specific inspection handler
from app.clients.magen.inbound import handle_inbound as magen_inspection_handler

from app.modules.survey import handler as survey_handler

from app.modules.announcements.admin_announcements_media_handler import (
    handle_media_message as announcements_media_handler,
)

logger = logging.getLogger("inbound.dispatcher")


# --------------------------------------------------
# DB Reset Guard
# --------------------------------------------------
def _reset_session(db: Session) -> None:
    try:
        db.rollback()
    except Exception as e:
        logger.warning("DB_ROLLBACK_FAIL | err=%s", str(e))


# --------------------------------------------------
# Client Resolution
# --------------------------------------------------
def _resolve_uuid_client_id(
    db: Session,
    *,
    business_msisdn: str,
) -> str | None:

    row = (
        db.execute(
            text(
                """
                SELECT client_id
                FROM whatsapp_numbers
                WHERE destination_number = :business
                  AND status = 'active'
                LIMIT 1
                """
            ),
            {"business": business_msisdn},
        )
        .mappings()
        .first()
    )

    if not row:
        logger.error(
            "CLIENT_RESOLUTION_FAIL | business_msisdn=%s not mapped",
            business_msisdn,
        )
        return None

    logger.info(
        "CLIENT_RESOLVED | business_msisdn=%s | client_id=%s",
        business_msisdn,
        row["client_id"],
    )

    return str(row["client_id"])


# --------------------------------------------------
# Dispatch
# --------------------------------------------------
def dispatch(*, db: Session, msg: dict, sender: str, business_msisdn: str) -> bool:

    logger.info(
        "DISPATCH_ENTER | sender=%s | business=%s | msg_type=%s",
        sender,
        business_msisdn,
        msg.get("type"),
    )

    if not msg:
        logger.warning("EMPTY_MESSAGE_RECEIVED | sender=%s", sender)
        return True

    _reset_session(db)

    client_id = _resolve_uuid_client_id(
        db,
        business_msisdn=business_msisdn,
    )

    if client_id is None:
        return True

    profile = get_client_profile(business_msisdn, db=db)

    if not profile:
        logger.error(
            "PROFILE_RESOLUTION_FAIL | business_msisdn=%s | client_id=%s",
            business_msisdn,
            client_id,
        )
        return True

    logger.info(
        "PROFILE_RESOLVED | client_id=%s | client_code=%s | enabled_modules=%s",
        client_id,
        profile.client_code,
        profile.enabled_modules,
    )

    # --------------------------------------------------
    # TEXT HANDLING
    # --------------------------------------------------
    if msg.get("type") == "text":
        body_text = (msg.get("text", {}) or {}).get("body", "").strip()

        logger.info(
            "TEXT_RECEIVED | sender=%s | body='%s'",
            sender,
            body_text,
        )

        # ---- Feedback ----
        if body_text.lower().startswith("feedback:"):
            logger.info("FEEDBACK_BRANCH_ENTER")

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

            handled = handle_feedback_message(
                db=db,
                sender_number=sender,
                message_text=body_text,
                media_id=None,
                media_type=None,
                client_id=client_id,
                admin_numbers=admin_numbers,
                business_msisdn=business_msisdn,
            )

            logger.info("FEEDBACK_HANDLED=%s", handled)

            if handled:
                return True

        # ---- GALITOS ORDERS ----
        if profile.client_code == "GALITOS":
            logger.info("GALITOS_BRANCH_ENTER")

            handled = galitos_order_handler.handle_order_message(
                db=db,
                from_number=sender,
                message_text=body_text,
                context={"business_msisdn": business_msisdn},
            )

            logger.info("GALITOS_HANDLED=%s", handled)

            if handled:
                return True

    # --------------------------------------------------
    # ANNOUNCEMENTS
    # --------------------------------------------------
    if "announcements" in profile.enabled_modules:
        logger.info("ANNOUNCEMENTS_BRANCH_ENTER")

        handled = announcements_media_handler(
            db=db,
            sender=sender,
            msg=msg,
            client_id=client_id,
            business_msisdn=business_msisdn,
        )

        logger.info("ANNOUNCEMENTS_HANDLED=%s", handled)

        if handled:
            return True

    # --------------------------------------------------
    # INSPECTION (Client-Specific: MAGEN)
    # --------------------------------------------------
    if "inspection" in profile.enabled_modules:
        logger.info(
            "INSPECTION_BRANCH_ENTER | client_code=%s",
            profile.client_code,
        )

        if profile.client_code in ("MAGEN", "Magen Security"):
            handled = magen_inspection_handler(
                db=db,
                msg=msg,
                sender=sender,
                business_msisdn=business_msisdn,
            )

            logger.info("MAGEN_INSPECTION_HANDLED=%s", handled)

            if handled:
                return True
        else:
            logger.info(
                "INSPECTION_NO_CLIENT_HANDLER | client_code=%s",
                profile.client_code,
            )
    else:
        logger.info("INSPECTION_BRANCH_SKIPPED")

    # --------------------------------------------------
    # SURVEY
    # --------------------------------------------------
    if "survey" in profile.enabled_modules:
        logger.info("SURVEY_BRANCH_ENTER")

        handled = survey_handler.handle(
            db=db,
            msg=msg,
            sender=sender,
            business_msisdn=business_msisdn,
        )

        logger.info("SURVEY_HANDLED=%s", handled)

        if handled:
            return True

    # --------------------------------------------------
    # TIER1 FALLBACK
    # --------------------------------------------------
    logger.warning(
        "FALLBACK_TRIGGERED | client_id=%s | sender=%s | msg_type=%s",
        client_id,
        sender,
        msg.get("type"),
    )

    body = (msg.get("text", {}) or {}).get("body", "")

    return bool(
        tier1_handle(
            db=db,
            sender_number=sender,
            message_text=body,
            msg=msg,
            resolved_client_id=client_id,
            resolved_business_number=business_msisdn,
        )
    )
