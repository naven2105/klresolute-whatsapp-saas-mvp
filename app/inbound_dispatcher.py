from __future__ import annotations

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.profiles.client_profile import get_client_profile
from app.handlers.tier1_router import handle_client_command as tier1_handle
from app.handlers.feedback_handler import handle_feedback_message

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
    except Exception:
        logger.debug("DISPATCH_DB_SESSION_RESET_SKIPPED")


def _resolve_integer_client_id(
    db: Session,
    *,
    business_msisdn: str,
) -> int | None:

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

        return int(row["klresolute_client_id"])

    except Exception:
        logger.exception(
            "DISPATCH_CLIENT_ID_LOOKUP_EXCEPTION | business=%s",
            business_msisdn,
        )
        return None


def _resolve_uuid_client_id(db: Session, integer_client_id: int) -> str | None:
    """
    Resolve UUID client_id from clients table using integer id.
    """
    try:
        row = (
            db.execute(
                text(
                    """
                    SELECT id
                    FROM clients
                    WHERE klresolute_client_id = :int_id
                    LIMIT 1
                    """
                ),
                {"int_id": integer_client_id},
            )
            .mappings()
            .first()
        )

        if not row:
            logger.error(
                "DISPATCH_UUID_LOOKUP_FAIL | integer_id=%s",
                integer_client_id,
            )
            return None

        logger.info(
            "DISPATCH_UUID_RESOLVED | integer_id=%s | uuid=%s",
            integer_client_id,
            row["id"],
        )

        return str(row["id"])

    except Exception:
        logger.exception(
            "DISPATCH_UUID_LOOKUP_EXCEPTION | integer_id=%s",
            integer_client_id,
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

    profile = get_client_profile(business_msisdn, db=db)
    if not profile:
        logger.error(
            "DISPATCH_ABORTED | stage=profile_resolution | business=%s | sender=%s",
            business_msisdn,
            sender,
        )
        return True

    # ----------------------------------
    # FEEDBACK
    # ----------------------------------
    if msg.get("type") == "text":
        body_text = (msg.get("text", {}) or {}).get("body", "")
        if body_text.strip().lower().startswith("feedback"):

            uuid_client_id = _resolve_uuid_client_id(
                db,
                resolved_client_id,
            )

            if uuid_client_id is None:
                return True

            handled = handle_feedback_message(
                db=db,
                sender_number=sender,
                message_text=body_text,
                media_id=None,
                media_type=None,
                client_id=uuid_client_id,
                admin_numbers=set(),
            )

            return bool(handled)

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
