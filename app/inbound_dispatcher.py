from __future__ import annotations

"""
File: app/inbound_dispatcher.py
Project: KLResolute WhatsApp SaaS MVP

Sprint 13 – Client Feedback Isolation

Purpose:
Central inbound routing entry point.

LOCKED:
- No business logic
- No module rewrites
- Only routing + logging
- Guard rails for visibility

Update:
- Removed shared feedback handler
- Feedback now routed per client folder
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.profiles.client_profile import get_client_profile
from app.handlers.tier1_router import handle_client_command as tier1_handle
from app.handlers import galitos_order_handler

# Client-specific feedback handlers
from app.clients.galitos.feedback.handler import handle_feedback_message as galitos_feedback_handler
from app.clients.fatginger.feedback.handler import handle_feedback_message as fatginger_feedback_handler
from app.clients.pilateshq.feedback.handler import handle_feedback_message as pilates_feedback_handler
from app.clients.magen.feedback.handler import handle_feedback_message as magen_feedback_handler

# Client-specific inspection handler
from app.clients.magen.inbound import handle_inbound as magen_inspection_handler

# Client-specific inbound
from app.clients.fatginger.inbound import handle_fatginger_inbound

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

    try:
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

        client_id = str(row["client_id"])

        logger.info(
            "CLIENT_RESOLVED | business_msisdn=%s | client_id=%s",
            business_msisdn,
        )

        return client_id

    except Exception:
        logger.exception(
            "CLIENT_RESOLUTION_EXCEPTION | business_msisdn=%s",
            business_msisdn,
        )
        return None


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
        logger.error(
            "DISPATCH_ABORT | client_unresolved | business=%s",
            business_msisdn,
        )
        return True

    profile = get_client_profile(business_msisdn, db=db)

    if not profile:
        logger.error(
            "PROFILE_RESOLUTION_FAIL | business=%s | client_id=%s",
            business_msisdn,
            client_id,
        )
        return True

    logger.info(
        "PROFILE_RESOLVED | client_id=%s | client_code=%s | modules=%s",
        profile.client_id,
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

            if profile.client_code == "GALITOS":
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

            elif profile.client_code == "FATGINGER":
                handled = fatginger_feedback_handler(
                    db=db,
                    sender_number=sender,
                    message_text=body_text,
                    media_id=None,
                    media_type=None,
                    client_id=client_id,
                    admin_numbers=admin_numbers,
                    business_msisdn=business_msisdn,
                )

            elif profile.client_code == "PILATESHQ":
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

            elif profile.client_code == "MAGEN":
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

            else:
                logger.warning("FEEDBACK_SKIP | unknown_client=%s", profile.client_code)
                handled = False

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

        # ---- FAT GINGER MENU ----
        if profile.client_code == "FATGINGER":
            logger.info("FATGINGER_BRANCH_ENTER")

            handled = handle_fatginger_inbound(
                db=db,
                sender_msisdn=sender,
                business_msisdn=business_msisdn,
                message_text=body_text,
            )

            logger.info("FATGINGER_HANDLED=%s", handled)

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
    # INSPECTION
    # --------------------------------------------------
    if "inspection" in profile.enabled_modules:
        logger.info(
            "INSPECTION_BRANCH_ENTER | client_code=%s",
            profile.client_code,
        )

        try:
            handled = magen_inspection_handler(
                db=db,
                msg=msg,
                sender=sender,
                business_msisdn=business_msisdn,
            )

            logger.info("INSPECTION_HANDLER_RETURN=%s", handled)

            if handled:
                return True

        except Exception:
            logger.exception(
                "INSPECTION_HANDLER_EXCEPTION | client_code=%s",
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