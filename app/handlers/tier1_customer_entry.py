from __future__ import annotations

"""
File: app/handlers/tier1_customer_entry.py
Path: app/handlers/tier1_customer_entry.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Handle Tier-1 CUSTOMER flow only.

GUARDS (LOCKED):
- Requires resolved INTEGER client_id
- Must NOT handle admin logic
- Must NOT intercept YES / NO
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.modules.status.reader import get_active_status
from app.clients.galitos.customer_commands import (
    handle_client_command as handle_customer_commands,
)

logger = logging.getLogger("handlers.tier1.customer")


# -------------------------------------------------
# Helpers
# -------------------------------------------------

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
                {"client_id": client_id, "contact": contact_number},
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
            {"client_id": client_id, "contact": contact_number},
        )
        db.commit()

        logger.info(
            "CUSTOMER_JOIN_INSERTED | client_id=%s | contact=%s",
            client_id,
            contact_number,
        )

    except Exception:
        db.rollback()
        logger.exception(
            "CUSTOMER_JOIN_FAIL | client_id=%s | contact=%s",
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
            "CLIENT_ID_PARSE_FAIL | value=%r",
            resolved_client_id,
        )
        return None


# -------------------------------------------------
# Public entry
# -------------------------------------------------

def handle_customer_entry(
    *,
    db: Session,
    sender_number: str,
    message_text: str,
    msg: dict | None,
    resolved_client_id: str | None,
    business_msisdn: str | None,
) -> bool:
    client_id_int = _parse_client_id(resolved_client_id)
    if client_id_int is None:
        logger.error(
            "CUSTOMER_BLOCKED | reason=invalid_client_id | sender=%s",
            sender_number,
        )
        return True

    _ensure_client_contact(
        db,
        client_id=client_id_int,
        contact_number=sender_number,
    )

    # ----------------------------------
    # Status read (pre-menu)
    # ----------------------------------
    if business_msisdn:
        status_text = get_active_status(
            db=db,
            business_msisdn=business_msisdn,
        )
        if status_text:
            logger.info(
                "STATUS_SENT | business=%s | sender=%s",
                business_msisdn,
                sender_number,
            )
            handle_customer_commands(
                db=db,
                sender=sender_number,
                msg={"type": "text", "text": {"body": status_text}},
                client_id=str(client_id_int),
                business_msisdn=business_msisdn,
            )

    # ----------------------------------
    # Normal customer flow
    # ----------------------------------
    return bool(
        handle_customer_commands(
            db=db,
            sender=sender_number,
            msg=msg or {"type": "text", "text": {"body": message_text}},
            client_id=str(client_id_int),
            business_msisdn=business_msisdn or "",
        )
    )
