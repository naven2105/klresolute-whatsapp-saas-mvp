from __future__ import annotations

"""
File: app/inbound_dispatcher.py
Project: KLResolute WhatsApp SaaS MVP

Sprint: Identity Stabilisation (UUID Canonicalisation)

Purpose:
Central inbound routing entry point.

Routing Model (MVP):
- Explicit command routing only
- Unknown command → Tier1 fallback

Patch (Inspection Consolidation):
- Generic inspection module removed
- Magen inspection routed explicitly to client-bound handler
- No other routing behaviour changed

Guard Rails:
- Fail-safe DB rollback on entry
- Explicit logging for inspection routing
- No silent routing failures
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.profiles.client_profile import get_client_profile
from app.handlers.tier1_router import handle_client_command as tier1_handle
from app.handlers.feedback_handler import handle_feedback_message
from app.handlers import galitos_order_handler

# ❌ Removed: from app.modules.inspection import handler as inspection_handler
# ✅ Client-bound inspection handler
from app.clients.magen.inbound import handle_inbound as magen_inspection_handler

from app.modules.survey import handler as survey_handler

from app.modules.announcements.admin_announcements_media_handler import (
    handle_media_message as announcements_media_handler,
)

logger = logging.getLogger("inbound.dispatcher")


def _reset_session(db: Session) -> None:
    try:
        db.rollback()
    except Exception as e:
        logger.warning("DB rollback failed during inbound reset | err=%s", str(e))


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
            "CLIENT_RESOLUTION_FAIL | business_msisdn=%s not mapped to active client",
            business_msisdn,
        )
        return None

    return str(row["client_id"])


def dispatch(*, db: Session, msg: dict, sender: str, business_msisdn: str) -> bool:

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
            "PROFILE_RESOLUTION_FAIL | business_msisdn=%s client_id=%s",
            business_msisdn,
            client_id,
        )
        return True

    # --------------------------------------------------
    # TEXT HANDLING
    # --------------------------------------------------
    if msg.get("type") == "text":
        body_text = (msg.get("text", {}) or {}).get("body", "").strip()

        if body_text:
            logger.info(
                "INBOUND_TEXT | client_id=%s sender=%s body=%s",
                client_id,
                sender,
                body_text,
            )

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

            if handled:
                logger.info("FEEDBACK_HANDLED | client_id=%s", client_id)
                return True

        # ---- GALITOS ORDERS (Direct Handler) ----
        if profile.client_code == "GALITOS":
            handled = galitos_order_handler.handle_order_message(
                db=db,
                from_number=sender,
                message_text=body_text,
                context={"business_msisdn": business_msisdn},
            )

            if handled:
                logger.info("GALITOS_ORDER_HANDLED | client_id=%s", client_id)
                return True

    # --------------------------------------------------
    # ANNOUNCEMENTS
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
            logger.info("ANNOUNCEMENTS_HANDLED | client_id=%s", client_id)
            return True

    # --------------------------------------------------
    # INSPECTION (Client-Bounded: MAGEN ONLY)
    # --------------------------------------------------
    if profile.client_code == "Magen Security" and "inspection" in profile.enabled_modules:
        logger.info(
            "INSPECTION_ROUTING_ATTEMPT | client_id=%s sender=%s",
            client_id,
            sender,
        )

        try:
            handled = magen_inspection_handler(
                db=db,
                msg=msg,
                sender=sender,
                business_msisdn=business_msisdn,
            )
        except Exception:
            logger.exception(
                "MAGEN_INSPECTION_HANDLER_FATAL | client_id=%s sender=%s",
                client_id,
                sender,
            )
            raise  # Fail hard — inspection integrity critical

        if handled:
            logger.info("MAGEN_INSPECTION_HANDLED | client_id=%s", client_id)
            return True

        logger.warning(
            "MAGEN_INSPECTION_NOT_HANDLED | client_id=%s sender=%s",
            client_id,
            sender,
        )

    # --------------------------------------------------
    # SURVEY
    # --------------------------------------------------
    if "survey" in profile.enabled_modules:
        handled = survey_handler.handle(
            db=db,
            msg=msg,
            sender=sender,
            business_msisdn=business_msisdn,
        )
        if handled:
            logger.info("SURVEY_HANDLED | client_id=%s", client_id)
            return True

    # --------------------------------------------------
    # TIER1 FALLBACK
    # --------------------------------------------------
    body = (msg.get("text", {}) or {}).get("body", "")

    logger.info("TIER1_FALLBACK | client_id=%s sender=%s", client_id, sender)

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
