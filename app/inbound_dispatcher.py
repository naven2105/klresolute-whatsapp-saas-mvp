# ==================================================
# File: inbound_dispatcher.py
# pathe: app/inbound_dispatcher.py
# Project: KLResolute WhatsApp SaaS MVP
# ==================================================

from __future__ import annotations

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.profiles.client_profile import get_client_profile

# Tenant dispatchers
from app.clients.fatginger.dispatcher import dispatch as fatginger_dispatch
from app.clients.rusticbarrel.dispatcher import dispatch as rusticbarrel_dispatch
from app.clients.magen.dispatcher import dispatch as magen_dispatch
from app.clients.pilateshq.dispatcher import dispatch as pilates_dispatch
from app.clients.zar.dispatcher import dispatch as zar_dispatch
from app.clients.periperi.dispatcher import dispatch as periperi_dispatch
from app.clients.klr_demo.dispatcher import dispatch as klr_demo_dispatch  # ✅ ADDED

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
        "PROFILE_RESOLVED | client_id=%s",
        client_id,
    )

    # --------------------------------------------------
    # TENANT ROUTING (UUID HARD ISOLATION)
    # --------------------------------------------------

    if client_id == "254d478e-da3a-4239-be94-c26aa75d30c0":
        return fatginger_dispatch(
            db=db,
            msg=msg,
            sender=sender,
            business_msisdn=business_msisdn,
            profile=profile,
            client_id=client_id,
        )

    # ✅ PeriPeri (correct — own dispatcher)
    if client_id == "09178be4-23b9-4650-bcbb-f5fb2cf32a18":
        return periperi_dispatch(
            db=db,
            msg=msg,
            sender=sender,
            business_msisdn=business_msisdn,
            profile=profile,
            client_id=client_id,
        )

    # ✅ KLR Demo (copy of Peri Peri)
    if client_id == "6e9d6052-535c-4dab-971b-48fb203705ca":
        return klr_demo_dispatch(
            db=db,
            msg=msg,
            sender=sender,
            business_msisdn=business_msisdn,
            profile=profile,
            client_id=client_id,
        )

    if client_id == "906a5084-1add-4b7a-bda0-90b462c9b8a9":
        return rusticbarrel_dispatch(
            db=db,
            msg=msg,
            sender=sender,
            business_msisdn=business_msisdn,
            profile=profile,
            client_id=client_id,
        )

    if client_id == "8e62632d-d778-4d18-818c-4ffec0532d47":
        return magen_dispatch(
            db=db,
            msg=msg,
            sender=sender,
            business_msisdn=business_msisdn,
            profile=profile,
            client_id=client_id,
        )

    if client_id == "405c3e31-3894-4f69-b219-fe19ed3fb362":
        return pilates_dispatch(
            db=db,
            msg=msg,
            sender=sender,
            business_msisdn=business_msisdn,
            profile=profile,
            client_id=client_id,
        )

    if client_id == "f306ff09-e231-43db-928b-b2f369338612":
        return zar_dispatch(
            db=db,
            msg=msg,
            sender=sender,
            business_msisdn=business_msisdn,
            profile=profile,
            client_id=client_id,
        )

    logger.warning(
        "UNKNOWN_CLIENT_ID | business=%s | client_id=%s",
        business_msisdn,
        client_id,
    )

    return True