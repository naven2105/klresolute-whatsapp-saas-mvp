from __future__ import annotations

"""
File: app/handlers/tier1_router.py
Path: app/handlers/tier1_router.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Tier-1 Router (Client + Admin entry point)

LOCKED GUARDS:
- MUST NOT handle order flow
- MUST NOT intercept YES / NO
- MUST NOT require profile DB for orders
- Admin must ALWAYS receive a response

DB TRUTH:
- client_contacts.client_id is INTEGER
- Tier-1 only uses resolved integer client_id
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.outbound.factory import get_meta_client
from app.utils.admin import is_admin_message
from app.handlers.admin_menu_builder import build_admin_menu
from app.modules.status.reader import get_active_status

from app.clients.galitos.customer_commands import (
    handle_client_command as handle_customer_commands,
)

logger = logging.getLogger("handlers.tier1_router")


# -------------------------------------------------
# Helpers
# -------------------------------------------------

def _send_text(*, business_number: str | None, to_number: str, text_msg: str) -> None:
    if not business_number:
        logger.error(
            "TIER1_SEND_BLOCKED | reason=missing_business_number | to=%s",
            to_number,
        )
        return

    meta = get_meta_client(business_msisdn=business_number)
    meta.send_session_message(
        to_msisdn=to_number,
        text=text_msg,
    )


def _ensure_client_contact(
    db: Session,
    *,
    client_id: int,
    contact_number: str,
) -> None:
    try:
        row = (
            db.execute(
                text(
                    """
                    SELECT 1
                    FROM client_contacts
                    WHERE client_id = :client_id
                      AND contact_number = :contact
                    LIMIT 1
                    """
                ),
                {
                    "client_id": client_id,
                    "contact": contact_number,
                },
            )
            .first()
        )

        if row:
            return

        db.execute(
            text(
                """
                INSERT INTO client_contacts (
                    client_id,
                    contact_number,
                    is_opted_out,
                    created_at
                )
                VALUES (
                    :client_id,
                    :contact,
                    FALSE,
                    now()
                )
                """
            ),
            {
                "client_id": client_id,
                "contact": contact_number,
            },
        )
        db.commit()

        logger.info(
            "CLIENT_SILENT_JOIN | client_id=%s | contact=%s",
            client_id,
            contact_number,
        )

    except Exception:
        db.rollback()
        logger.exception(
            "CLIENT_SILENT_JOIN_FAIL | client_id=%s | contact=%s",
            client_id,
            contact_number,
        )


def _parse_client_id(resolved_client_id: str | None) -> int | None:
    if not resolved_client_id:
        return None
    try:
        return int(resolved_client_id)
    except Exception:
        logger.exception(
            "CLIENT_ID_PARSE_FAIL | raw=%r",
            resolved_client_id,
        )
        return None


# -------------------------------------------------
# Main handler
# -------------------------------------------------

def handle_client_command(
    *,
    db: Session,
    sender_number: str,
    message_text: str,
    msg: dict | None = None,
    resolved_client_id: str | None = None,
    resolved_business_number: str | None = None,
    resolved_phone_number_id: str | None = None,
) -> bool:
    """
    Returns True if handled.
    """

    try:
        business_number = resolved_business_number
        upper = (message_text or "").strip().upper()

        # ----------------------------------
        # HARD ORDER GUARD
        # ----------------------------------
        if upper in ("YES", "NO"):
            return False

        # ----------------------------------
        # ADMIN CHECK
        # ----------------------------------
        is_admin = (
            business_number
            and is_admin_message(
                db=db,
                sender=sender_number,
                business_msisdn=business_number,
            )
        )

        # =================================================
        # ADMIN PATH — GUARANTEED RESPONSE
        # =================================================
        if is_admin:
            logger.info(
                "TIER1_ADMIN_MESSAGE | sender=%s | text=%r",
                sender_number,
                message_text,
            )

            admin_menu = build_admin_menu(
                db=db,
                business_msisdn=business_number,
            )

            _send_text(
                business_number=business_number,
                to_number=sender_number,
                text_msg=admin_menu,
            )
            return True

        # =================================================
        # CUSTOMER PATH
        # =================================================
        client_id_int = _parse_client_id(resolved_client_id)
        if client_id_int is None:
            logger.error(
                "CUSTOMER_BLOCKED | reason=client_id_missing | sender=%s",
                sender_number,
            )
            return True

        # ----------------------------------
        # ABOUT (recognised, delegated)
        # ----------------------------------
        if upper == "ABOUT":
            logger.info(
                "TIER1_ABOUT_DELEGATED | sender=%s | client_id=%s",
                sender_number,
                client_id_int,
            )
            # fall through intentionally

        _ensure_client_contact(
            db,
            client_id=client_id_int,
            contact_number=sender_number,
        )

        # ----------------------------------
        # STATUS NOTICE (if active)
        # ----------------------------------
        status_text = (
            get_active_status(
                db=db,
                business_msisdn=business_number,
            )
            if business_number
            else None
        )

        if status_text:
            _send_text(
                business_number=business_number,
                to_number=sender_number,
                text_msg=f"⚠️ NOTICE\n\n{status_text}\n\n———",
            )

        handled = handle_customer_commands(
            db=db,
            sender=sender_number,
            msg=msg
            or {"type": "text", "text": {"body": message_text or ""}},
            client_id=str(client_id_int),
            business_msisdn=business_number or "",
        )

        if not handled:
            logger.warning(
                "TIER1_CUSTOMER_UNHANDLED | sender=%s | text=%r",
                sender_number,
                message_text,
            )

        return bool(handled)

    except Exception:
        logger.exception(
            "TIER1_FATAL | sender=%s",
            sender_number,
        )
        return True
