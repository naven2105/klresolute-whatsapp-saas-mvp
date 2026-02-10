from __future__ import annotations

"""
File: app/inbound_dispatcher.py
Path: app/inbound_dispatcher.py
Project: KLResolute WhatsApp SaaS MVP

ROLE (EXPLICIT & LOCKED):
Inbound dispatcher and module router.

RESPONSIBILITY:
- Resolve client + profile
- Route inbound messages to enabled modules
- Delegate behaviour (no business logic here)

GUARD RAILS (MANDATORY):
- MUST NEVER raise exceptions
- MUST NEVER break caller flow
- MUST fail safe and log clearly (Render-first)
- MUST NOT mutate business behaviour

NOTES:
- Broadcast module is PAUSED
- Specials admin upload is handled as a module
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.profiles.client_profile import get_client_profile
from app.handlers.tier1_router import handle_client_command as tier1_handle

from app.modules.orders import handler as orders_handler
from app.modules.inspection import handler as inspection_handler
from app.modules.survey import handler as survey_handler
from app.modules.specials.admin_specials_media_handler import (
    handle_media_message as specials_media_handler,
)

logger = logging.getLogger("inbound.dispatcher")


# -------------------------------------------------
# Helpers
# -------------------------------------------------

def _reset_session(db: Session) -> None:
    try:
        db.rollback()
        logger.debug("DISPATCH_DB_SESSION_RESET | action=rollback")
    except Exception as exc:
        logger.debug(
            "DISPATCH_DB_SESSION_RESET_SKIPPED | err=%s",
            exc,
        )


def _resolve_integer_client_id(
    db: Session,
    *,
    business_msisdn: str,
) -> int | None:
    """
    Resolve MVP integer client_id via whatsapp_numbers.klresolute_client_id
    """
    logger.info(
        "DISPATCH_CLIENT_ID_LOOKUP_ENTER | business=%s",
        business_msisdn,
    )

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
                "DISPATCH_CLIENT_ID_LOOKUP_FAIL | business=%s",
                business_msisdn,
            )
            return None

        client_id_int = int(row["klresolute_client_id"])
        logger.info(
            "DISPATCH_CLIENT_ID_RESOLVED | business=%s | client_id=%s",
            business_msisdn,
            client_id_int,
        )
        return client_id_int

    except Exception as exc:
        logger.exception(
            "DISPATCH_CLIENT_ID_LOOKUP_EXCEPTION | business=%s | err=%s",
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

    if not msg:
        logger.error(
            "DISPATCH_ABORTED | reason=msg_none | sender=%s | business=%s",
            sender,
            business_msisdn,
        )
        return True

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
            "DISPATCH_ABORTED | stage=client_id_resolution | business=%s | sender=%s",
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
            "DISPATCH_ABORTED | stage=profile_resolution | business=%s | sender=%s",
            business_msisdn,
            sender,
        )
        return True

    logger.info(
        "DISPATCH_PROFILE_RESOLVED | client_code=%s | enabled_modules=%s",
        profile.client_code,
        ",".join(profile.enabled_modules),
    )

    # ----------------------------------
    # SPECIALS (ADMIN IMAGE UPLOAD)
    # ----------------------------------
    if (
        msg.get("type") == "image"
        and "specials" in profile.enabled_modules
    ):
        logger.info(
            "DISPATCH_CHECK_SPECIALS | client_code=%s | specials_enabled=True",
            profile.client_code,
        )
        try:
            handled = specials_media_handler(
                db=db,
                sender=sender,
                msg=msg,
                client_id=resolved_client_id,
                business_msisdn=business_msisdn,
            )
            logger.info(
                "DISPATCH_EXIT_SPECIALS | handled=%s",
                handled,
            )
            if handled:
                return True
        except Exception as exc:
            logger.exception(
                "DISPATCH_SPECIALS_FATAL | business=%s | sender=%s | err=%s",
                business_msisdn,
                sender,
                exc,
            )
            return True

    # ----------------------------------
    # ORDERS
    # ----------------------------------
    if profile.client_code == "GALITOS" and "orders" in profile.enabled_modules:
        handled = orders_handler.handle(
            db=db,
            msg=msg,
            sender=sender,
            business_msisdn=business_msisdn,
        )
        if handled:
            return True

    # ----------------------------------
    # INSPECTION
    # ----------------------------------
    if profile.client_code != "GALITOS" and "inspection" in profile.enabled_modules:
        handled = inspection_handler.handle(
            db=db,
            msg=msg,
            sender=sender,
            profile_code=profile.client_code,
        )
        if handled:
            return True

    # ----------------------------------
    # SURVEY
    # ----------------------------------
    if "survey" in profile.enabled_modules:
        handled = survey_handler.handle(
            db=db,
            msg=msg,
            sender=sender,
            business_msisdn=business_msisdn,
        )
        if handled:
            return True

    # ----------------------------------
    # Final fallback → Tier-1 router
    # ----------------------------------
    body = (msg.get("text", {}) or {}).get("body", "")
    return bool(
        tier1_handle(
            db=db,
            sender_number=sender,
            message_text=body,
            msg=msg,
            resolved_client_id=str(resolved_client_id),
            resolved_business_number=business_msisdn,
        )
    )
