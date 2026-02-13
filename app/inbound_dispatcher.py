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
        return None

    return int(row["klresolute_client_id"])


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
        return None

    return str(row["client_id"])


def dispatch(*, db: Session, msg: dict, sender: str, business_msisdn: str) -> bool:

    if not msg:
        return True

    _reset_session(db)

    resolved_client_id = _resolve_integer_client_id(
        db,
        business_msisdn=business_msisdn,
    )

    if resolved_client_id is None:
        return True

    profile = get_client_profile(business_msisdn, db=db)
    if not profile:
        return True

    # ----------------------------------
    # FEEDBACK (UUID path)
    # ----------------------------------
    if msg.get("type") == "text":
        body_text = (msg.get("text", {}) or {}).get("body", "")
        if body_text.strip().lower().startswith("feedback"):

            uuid_client_id = _resolve_uuid_client_id(
                db,
                business_msisdn=business_msisdn,
            )

            if uuid_client_id is None:
                return True

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
                client_id=uuid_client_id,
                admin_numbers=admin_numbers,
            )

            return bool(handled)

    # ----------------------------------
    # SPECIALS (ADMIN MEDIA)  ← ADDED
    # ----------------------------------
    if "specials" in profile.enabled_modules:
        handled = specials_media_handler(
            db=db,
            sender=sender,
            msg=msg,
            client_id=resolved_client_id,
            business_msisdn=business_msisdn,
        )
        if handled:
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
