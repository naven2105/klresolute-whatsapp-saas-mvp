from __future__ import annotations

"""
File: app/inbound_dispatcher.py
Path: app/inbound_dispatcher.py
Project: KLResolute WhatsApp SaaS MVP

LOCKED:
- No DB writes
- Behaviour defined by handlers

MVP RULE:
- resolved_client_id MUST be INTEGER (klresolute_client_id)

STATUS:
- Broadcast module is PAUSED
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.profiles.client_profile import get_client_profile
from app.handlers.tier1_router import handle_client_command as tier1_handle

from app.modules.orders import handler as orders_handler
from app.modules.inspection import handler as inspection_handler
from app.modules.survey import handler as survey_handler
# from app.modules.broadcast import handler as broadcast_handler  # PAUSED

logger = logging.getLogger("inbound.dispatcher")


# -------------------------------------------------
# Helpers
# -------------------------------------------------

def _reset_session(db: Session) -> None:
    try:
        db.rollback()
        logger.debug("DISPATCH_DB_SESSION_RESET")
    except Exception:
        logger.debug("DISPATCH_DB_SESSION_RESET_SKIPPED")


def _resolve_integer_client_id(
    db: Session,
    *,
    business_msisdn: str,
) -> int | None:
    """
    Resolve MVP integer client_id via whatsapp_numbers.klresolute_client_id
    """
    try:
        row = (
            db.execute(
                text(
                    """
                    SELECT klresolute_client_id
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
                "DISPATCH_CLIENT_ID_ROW_NOT_FOUND | business=%s",
                business_msisdn,
            )
            return None

        if row["klresolute_client_id"] is None:
            logger.error(
                "DISPATCH_CLIENT_ID_NULL | business=%s",
                business_msisdn,
            )
            return None

        client_id_int = int(row["klresolute_client_id"])
        logger.info(
            "DISPATCH_CLIENT_ID_INT_RESOLVED | business=%s | client_id=%s",
            business_msisdn,
            client_id_int,
        )
        return client_id_int

    except Exception as exc:
        logger.exception(
            "DISPATCH_CLIENT_ID_INT_RESOLUTION_FAIL | business=%s | err=%s",
            business_msisdn,
            exc,
        )
        return None


# -------------------------------------------------
# Dispatcher
# -------------------------------------------------

def dispatch(*, db: Session, msg: dict, sender: str, business_msisdn: str) -> bool:
    logger.info(
        "DISPATCH_ENTER | sender=%s | business=%s | msg_type=%s",
        sender,
        business_msisdn,
        msg.get("type"),
    )

    _reset_session(db)

    # ----------------------------------
    # Resolve integer client_id (MVP)
    # ----------------------------------
    resolved_client_id = _resolve_integer_client_id(
        db,
        business_msisdn=business_msisdn,
    )

    if resolved_client_id is None:
        logger.error(
            "DISPATCH_ABORTED | stage=client_id | business=%s | sender=%s",
            business_msisdn,
            sender,
        )
        return True

    # ----------------------------------
    # Resolve profile (routing only)
    # ----------------------------------
    profile = get_client_profile(business_msisdn, db=db)
    if not profile:
        logger.error(
            "DISPATCH_ABORTED | stage=profile | business=%s | sender=%s",
            business_msisdn,
            sender,
        )
        return True

    logger.info(
        "DISPATCH_PROFILE_OK | client_code=%s | modules=%s",
        profile.client_code,
        ",".join(profile.enabled_modules),
    )

    # ----------------------------------
    # ORDERS (Galitos only)
    # ----------------------------------
    logger.debug("DISPATCH_CHECK_ORDERS")
    if profile.client_code == "GALITOS" and "orders" in profile.enabled_modules:
        logger.info("DISPATCH_ENTER_ORDERS")
        handled = orders_handler.handle(
            db=db,
            msg=msg,
            sender=sender,
            business_msisdn=business_msisdn,
        )
        logger.info(
            "DISPATCH_EXIT_ORDERS | handled=%s",
            handled,
        )
        if handled:
            return True
    else:
        logger.info(
            "DISPATCH_SKIP_ORDERS | client_code=%s | orders_enabled=%s",
            profile.client_code,
            "orders" in profile.enabled_modules,
        )

    # ----------------------------------
    # INSPECTION (non-Galitos only)
    # ----------------------------------
    logger.debug("DISPATCH_CHECK_INSPECTION")
    if profile.client_code != "GALITOS" and "inspection" in profile.enabled_modules:
        logger.info("DISPATCH_ENTER_INSPECTION")
        handled = inspection_handler.handle(
            db=db,
            msg=msg,
            sender=sender,
            profile_code=profile.client_code,
        )
        logger.info(
            "DISPATCH_EXIT_INSPECTION | handled=%s",
            handled,
        )
        if handled:
            return True

    # ----------------------------------
    # SURVEY
    # ----------------------------------
    logger.debug("DISPATCH_CHECK_SURVEY")
    if "survey" in profile.enabled_modules:
        logger.info("DISPATCH_ENTER_SURVEY")
        handled = survey_handler.handle(
            db=db,
            msg=msg,
            sender=sender,
            business_msisdn=business_msisdn,
        )
        logger.info(
            "DISPATCH_EXIT_SURVEY | handled=%s",
            handled,
        )
        if handled:
            return True

    # ----------------------------------
    # BROADCAST (PAUSED)
    # ----------------------------------
    if "broadcast" in profile.enabled_modules:
        logger.warning(
            "DISPATCH_MODULE_SKIPPED | module=broadcast | reason=paused | business=%s | sender=%s",
            business_msisdn,
            sender,
        )

    # ----------------------------------
    # Final fallback → Tier-1 router
    # ----------------------------------
    logger.info(
        "DISPATCH_FALLTHROUGH_TO_TIER1 | sender=%s | business=%s | client_code=%s",
        sender,
        business_msisdn,
        profile.client_code,
    )

    return bool(
        tier1_handle(
            db=db,
            sender_number=sender,
            message_text=(msg.get("text", {}) or {}).get("body", ""),
            msg=msg,
            resolved_client_id=str(resolved_client_id),
            resolved_business_number=business_msisdn,
        )
    )
