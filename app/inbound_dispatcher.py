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
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.profiles.client_profile import get_client_profile
from app.handlers.tier1_router import handle_client_command as tier1_handle

from app.modules.orders import handler as orders_handler
from app.modules.inspection import handler as inspection_handler
from app.modules.survey import handler as survey_handler
from app.modules.broadcast import handler as broadcast_handler

logger = logging.getLogger("inbound.dispatcher")


# -------------------------------------------------
# Helpers
# -------------------------------------------------

def _reset_session(db: Session) -> None:
    try:
        db.rollback()
    except Exception:
        pass


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

        if not row or row["klresolute_client_id"] is None:
            logger.error(
                "DISPATCH_CLIENT_ID_INT_NOT_FOUND | business=%s",
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
            "DISPATCH_ABORTED | reason=client_id_not_resolved | business=%s | sender=%s",
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
            "DISPATCH_ABORTED | reason=profile_not_resolved | business=%s | sender=%s",
            business_msisdn,
            sender,
        )
        return True

    # ----------------------------------
    # ORDERS (Galitos only)
    # ----------------------------------
    if profile.client_code == "GALITOS" and "orders" in profile.enabled_modules:
        if orders_handler.handle(
            db=db,
            msg=msg,
            sender=sender,
            business_msisdn=business_msisdn,
        ):
            return True

    # ----------------------------------
    # INSPECTION (non-Galitos only)
    # ----------------------------------
    if profile.client_code != "GALITOS" and "inspection" in profile.enabled_modules:
        if inspection_handler.handle(
            db=db,
            msg=msg,
            sender=sender,
            profile_code=profile.client_code,
        ):
            return True

    # ----------------------------------
    # Other modules
    # ----------------------------------
    if "survey" in profile.enabled_modules and survey_handler.handle(
        db=db,
        msg=msg,
        sender=sender,
        business_msisdn=business_msisdn,
    ):
        return True

    if "broadcast" in profile.enabled_modules and broadcast_handler.handle(
        db=db,
        msg=msg,
        sender=sender,
        business_msisdn=business_msisdn,
    ):
        return True

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
