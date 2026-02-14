from __future__ import annotations

"""
File: app/handlers/tier1_router.py
Path: app/handlers/tier1_router.py
Project: KLResolute WhatsApp SaaS MVP

Sprint: Full UUID Identity Migration

Purpose:
Tier-1 Router (Client + Admin entry point)

EXPLICIT ROLE:
- Single canonical entry point for admin + customer routing
- Admin menus are hard-coded per client
- No DB-driven menu construction

LOCKED GUARDS:
- MUST NOT handle order flow
- MUST NOT intercept YES / NO
- MUST NOT require profile DB for orders
- Admin must ALWAYS receive a response

DB TRUTH (UPDATED):
- client_contacts.client_id is UUID
- Tier-1 uses resolved UUID client_id only
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.messaging.client_messenger import send_message
from app.utils.admin import is_admin_message
from app.modules.status.reader import get_active_status

from app.clients.galitos.customer_commands import (
    handle_client_command as handle_customer_commands,
)

from app.handlers.tier1_admin_entry_galitos import handle_admin_entry
from app.services.contacts_service import add_contact

logger = logging.getLogger("handlers.tier1_router")


# -------------------------------------------------
# Helpers
# -------------------------------------------------

def _send_text(*, business_number: str | None, to_number: str, text_msg: str, db: Session) -> None:
    if not business_number:
        logger.error(
            "TIER1_SEND_BLOCKED | reason=missing_business_number | to=%s",
            to_number,
        )
        return

    try:
        send_message(
            db=db,
            business_msisdn=business_number,
            to_number=to_number,
            text=text_msg,
        )
    except Exception:
        logger.exception(
            "TIER1_SEND_FAIL | business=%s | to=%s",
            business_number,
            to_number,
        )


def _ensure_client_contact(
    db: Session,
    *,
    client_id: str,
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
                "TIER1_ADMIN_DELEGATE | sender=%s | text=%r",
                sender_number,
                message_text,
            )

            return handle_admin_entry(
                db=db,
                sender_number=sender_number,
                message_text=message_text,
                msg=msg,
                business_msisdn=business_number,
            )

        # =================================================
        # CUSTOMER PATH
        # =================================================
        if not resolved_client_id:
            logger.error(
                "CUSTOMER_BLOCKED | reason=client_id_missing | sender=%s",
                sender_number,
            )
            return True

        # ----------------------------------
        # GLOBAL CONTACT AUTO-JOIN (SILENT)
        # ----------------------------------
        try:
            add_contact(db, msisdn=sender_number)
        except Exception:
            logger.exception(
                "CONTACT_AUTO_JOIN_FAIL | sender=%s",
                sender_number,
            )

        if upper == "ABOUT":
            logger.info(
                "TIER1_ABOUT_DELEGATED | sender=%s | client_id=%s",
                sender_number,
                resolved_client_id,
            )

        _ensure_client_contact(
            db,
            client_id=resolved_client_id,
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
                db=db,
            )

        handled = handle_customer_commands(
            db=db,
            sender=sender_number,
            msg=msg
            or {"type": "text", "text": {"body": message_text or ""}},
            client_id=resolved_client_id,
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
