from __future__ import annotations

"""
File: app/modules/join/handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Handle client opt-in (JOIN) logic.

Responsibilities:
- Detect JOIN command
- Create client_contact if new
- Do NOT send any message
- Return True if handled

Scope:
- Client-facing only
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger("module.join")


def handle(*, db: Session, msg: dict, sender: str, business_msisdn: str) -> bool:
    logger.info(
        "JOIN_HANDLER_ENTERED | sender=%s | business=%s",
        sender,
        business_msisdn,
    )

    # ----------------------------------
    # Message validation
    # ----------------------------------
    if msg.get("type") != "text":
        return False

    body = msg.get("text", {}).get("body", "").strip()
    if body.upper() != "JOIN":
        return False

    # ----------------------------------
    # Resolve client via whatsapp_numbers
    # ----------------------------------
    try:
        client_row = (
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
    except Exception:
        logger.error(
            "JOIN_CLIENT_LOOKUP_FAILED | business=%s",
            business_msisdn,
            exc_info=True,
        )
        return True

    if not client_row:
        logger.error(
            "JOIN_CLIENT_NOT_FOUND | business=%s",
            business_msisdn,
        )
        return True

    client_id = client_row["klresolute_client_id"]

    # ----------------------------------
    # Client contact lookup / creation
    # ----------------------------------
    try:
        existing = (
            db.execute(
                text(
                    """
                    SELECT 1
                    FROM client_contacts
                    WHERE client_id = :client_id
                      AND contact_number = :sender
                    LIMIT 1
                    """
                ),
                {"client_id": client_id, "sender": sender},
            )
            .first()
        )

        if not existing:
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
                        :sender,
                        FALSE,
                        now()
                    )
                    """
                ),
                {"client_id": client_id, "sender": sender},
            )
            db.commit()

    except IntegrityError:
        db.rollback()
        logger.warning(
            "JOIN_CLIENT_CONTACT_RACE | sender=%s | client_id=%s",
            sender,
            client_id,
        )

    except Exception:
        db.rollback()
        logger.error(
            "JOIN_CLIENT_CONTACT_PERSIST_FAILED | sender=%s | client_id=%s",
            sender,
            client_id,
            exc_info=True,
        )

    logger.info(
        "JOIN_COMPLETED | sender=%s | client_id=%s",
        sender,
        client_id,
    )
    return True
