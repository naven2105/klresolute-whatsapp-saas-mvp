# ==================================================
# File: inbound_dispatcher.py
# Project: KLResolute WhatsApp SaaS MVP
#
# Sprint 17 – Tenant Isolation Refactor (Final Phase)
#
# Purpose:
# Central inbound routing entry point.
#
# Responsibilities:
# - Reset DB session
# - Resolve tenant (client_id + profile)
# - Route to tenant-specific dispatcher
# - Return immediately
#
# Isolation:
# - No business logic
# - No module execution
# - No cross-client routing
# - No fallback
# ==================================================

from __future__ import annotations

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.profiles.client_profile import get_client_profile

# Tenant dispatchers
from app.clients.fatginger.dispatcher import dispatch as fatginger_dispatch
from app.clients.galitos.dispatcher import dispatch as galitos_dispatch
from app.clients.magen.dispatcher import dispatch as magen_dispatch
from app.clients.pilateshq.dispatcher import dispatch as pilates_dispatch

logger = logging.getLogger("inbound.dispatcher")


def _reset_session(db: Session) -> None:
    try:
        db.rollback()
    except Exception as e:
        logger.warning("DB_ROLLBACK_FAIL | err=%s", str(e))


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

        return str(row["client_id"])

    except Exception:
        logger.exception(
            "CLIENT_RESOLUTION_EXCEPTION | business_msisdn=%s",
            business_msisdn,
        )
        return None


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
        "PROFILE_RESOLVED | client_id=%s | client_code=%s",
        profile.client_id,
        profile.client_code,
    )

    # --------------------------------------------------
    # TENANT ROUTING (HARD ISOLATION)
    # --------------------------------------------------

    if profile.client_code == "FATGINGER":
        return fatginger_dispatch(
            db=db,
            msg=msg,
            sender=sender,
            business_msisdn=business_msisdn,
            profile=profile,
            client_id=client_id,
        )

    if profile.client_code == "GALITOS":
        return galitos_dispatch(
            db=db,
            msg=msg,
            sender=sender,
            business_msisdn=business_msisdn,
            profile=profile,
            client_id=client_id,
        )

    if profile.client_code == "MAGEN":
        return magen_dispatch(
            db=db,
            msg=msg,
            sender=sender,
            business_msisdn=business_msisdn,
            profile=profile,
            client_id=client_id,
        )

    if profile.client_code == "PILATESHQ":
        return pilates_dispatch(
            db=db,
            msg=msg,
            sender=sender,
            business_msisdn=business_msisdn,
            profile=profile,
            client_id=client_id,
        )

    logger.warning(
        "UNKNOWN_CLIENT_CODE | business=%s | client_code=%s",
        business_msisdn,
        profile.client_code,
    )

    return True