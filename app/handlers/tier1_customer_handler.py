from __future__ import annotations

"""
File: app/handlers/tier1_customer_handler.py
Path: app/handlers/tier1_customer_handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Customer-specific Tier-1 handling.

Rules (LOCKED):
- Customers only (admins must not reach here)
- Uses INTEGER client_id only (klresolute_client_id)
- No UUID resolution here
- MUST NOT intercept YES / NO
- MUST NOT handle admin logic
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.clients.galitos.customer_commands import (
    handle_client_command as handle_customer_commands,
)

logger = logging.getLogger("handlers.tier1_customer")


# =================================================
# Helpers
# =================================================

def _parse_resolved_client_id_int(resolved_client_id: str | None) -> int | None:
    """
    Guarded parse for resolved integer client_id.
    """
    if not resolved_client_id or not str(resolved_client_id).strip():
        return None

    raw = str(resolved_client_id).strip()
    try:
        return int(raw)
    except Exception as exc:
        logger.exception(
            "CLIENT_ID_PARSE_FAIL | resolved_client_id=%r | err=%s",
            raw,
            exc,
        )
        return None


def _ensure_client_contact(
    db: Session,
    *,
    client_id: int,
    contact_number: str,
) -> None:
    """
    Silent JOIN (implicit).

    DB truth:
    - client_contacts.client_id is INTEGER
    """
    try:
        row = (
            db.execute(
                text(
                    """
                    SELECT is_opted_out
                    FROM client_contacts
                    WHERE client_id = :client_id
                      AND contact_number = :contact_number
                    LIMIT 1
                    """
                ),
                {"client_id": client_id, "contact_number": contact_number},
            )
            .mappings()
            .first()
        )

        if row:
            if bool(row.get("is_opted_out")) is True:
                logger.info(
                    "CUSTOMER_JOIN_SKIPPED_OPTED_OUT | client_id=%s | contact=%s",
                    client_id,
                    contact_number,
                )
                return

            logger.info(
                "CUSTOMER_JOIN_EXISTS | client_id=%s | contact=%s",
                client_id,
                contact_number,
            )
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
                    :contact_number,
                    FALSE,
                    now()
                )
                """
            ),
            {"client_id": client_id, "contact_number": contact_number},
        )
        db.commit()

        logger.info(
            "CUSTOMER_JOIN_INSERTED | client_id=%s | contact=%s",
            client_id,
            contact_number,
        )

    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass

        logger.exception(
            "CUSTOMER_JOIN_FAIL | client_id=%s | contact=%s | err=%s",
            client_id,
            contact_number,
            exc,
        )


# =================================================
# Main handler
# =================================================

def handle_customer_tier1(
    *,
    db: Session,
    sender_number: str,
    message_text: str,
    msg: dict | None,
    resolved_client_id: str | None,
    business_msisdn: str | None,
) -> bool:
    """
    Returns True if customer message was handled.
    """

    # ----------------------------------
    # Guard: resolved integer client_id
    # ----------------------------------
    client_id_int = _parse_resolved_client_id_int(resolved_client_id)

    if client_id_int is None:
        logger.error(
            "CUSTOMER_HANDLER_BLOCKED | reason=invalid_client_id | sender=%s | business=%s | resolved_client_id=%r",
            sender_number,
            business_msisdn,
            resolved_client_id,
        )
        return True  # hard stop

    logger.info(
        "CUSTOMER_HANDLER_ENTER | sender=%s | client_id=%s | business=%s",
        sender_number,
        client_id_int,
        business_msisdn,
    )

    # ----------------------------------
    # Silent join
    # ----------------------------------
    _ensure_client_contact(
        db,
        client_id=client_id_int,
        contact_number=sender_number,
    )

    # ----------------------------------
    # Delegate to customer commands
    # ----------------------------------
    return bool(
        handle_customer_commands(
            db=db,
            sender=sender_number,
            msg=msg or {"type": "text", "text": {"body": message_text or ""}},
            client_id=str(client_id_int),
            business_msisdn=business_msisdn or "",
        )
    )
