from __future__ import annotations

"""
File: app/modules/join/handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Handle client opt-in (JOIN) logic.

Responsibilities:
- Detect JOIN command
- Create contact if new
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

    # ----------------------------------
    # Contact lookup / creation
    # ----------------------------------
    try:
        contact = (
            db.execute(
                text(
                    """
                    SELECT 1
                    FROM contacts
                    WHERE contact_number = :sender
                    LIMIT 1
                    """
                ),
                {"sender": sender},
            )
            .first()
        )

        if not contact:
            db.execute(
                text(
                    """
                    INSERT INTO contacts (contact_id, contact_number)
                    VALUES (gen_random_uuid(), :sender)
                    """
                ),
                {"sender": sender},
            )
            db.commit()

    except IntegrityError:
        db.rollback()
        logger.warning(
            "JOIN_CONTACT_RACE_CONDITION | sender=%s",
            sender,
        )

    except Exception:
        db.rollback()
        logger.error(
            "JOIN_CONTACT_PERSIST_FAILED | sender=%s",
            sender,
            exc_info=True,
        )

    logger.info(
        "JOIN_COMPLETED | sender=%s",
        sender,
    )
    return True
