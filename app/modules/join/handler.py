from __future__ import annotations

"""
File: app/modules/join/handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Handle client opt-in (JOIN) logic.

Responsibilities:
- Detect JOIN command
- Create contact if new
- Send JOIN welcome message (DB-driven)
- Return True if handled

Scope:
- Client-facing only
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.outbound.factory import get_meta_client

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
        logger.debug("JOIN_SKIP | non-text message")
        return False

    body = msg.get("text", {}).get("body", "").strip()
    if body.upper() != "JOIN":
        logger.debug("JOIN_SKIP | not JOIN | body=%r", body)
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
    # Contact lookup / creation
    # ----------------------------------
    try:
        contact = (
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

        if not contact:
            db.execute(
                text(
                    """
                    INSERT INTO client_contacts (client_id, contact_number)
                    VALUES (:client_id, :sender)
                    """
                ),
                {"client_id": client_id, "sender": sender},
            )
            db.commit()
            logger.info(
                "JOIN_CONTACT_CREATED | sender=%s | client_id=%s",
                sender,
                client_id,
            )
        else:
            logger.info(
                "JOIN_CONTACT_EXISTS | sender=%s | client_id=%s",
                sender,
                client_id,
            )

    except IntegrityError:
        db.rollback()
        logger.warning(
            "JOIN_CONTACT_RACE_CONDITION | sender=%s | client_id=%s",
            sender,
            client_id,
        )

    except Exception:
        db.rollback()
        logger.error(
            "JOIN_CONTACT_PERSIST_FAILED | sender=%s | client_id=%s",
            sender,
            client_id,
            exc_info=True,
        )
        return True

    # ----------------------------------
    # JOIN welcome message (DB-driven)
    # ----------------------------------
    logger.info(
        "JOIN_WELCOME_LOOKUP_START | sender=%s | client_id=%s",
        sender,
        client_id,
    )

    try:
        row = (
            db.execute(
                text(
                    """
                    SELECT message_text
                    FROM client_onboarding_messages
                    WHERE client_id = :client_id
                      AND message_key = 'join_welcome'
                      AND is_active = TRUE
                    LIMIT 1
                    """
                ),
                {"client_id": client_id},
            )
            .mappings()
            .first()
        )
    except Exception:
        logger.error(
            "JOIN_WELCOME_LOOKUP_FAILED | sender=%s | client_id=%s",
            sender,
            client_id,
            exc_info=True,
        )
        return True

    logger.info(
        "JOIN_WELCOME_LOOKUP_DONE | sender=%s | found=%s",
        sender,
        bool(row),
    )

    if row:
        meta = get_meta_client()
        meta.send_session_message(
            to_msisdn=sender,
            text=row["message_text"],
        )
        logger.info(
            "JOIN_WELCOME_SENT | sender=%s | client_id=%s",
            sender,
            client_id,
        )
    else:
        logger.warning(
            "JOIN_WELCOME_MISSING | sender=%s | client_id=%s",
            sender,
            client_id,
        )

    logger.info(
        "JOIN_COMPLETED | sender=%s | client_id=%s",
        sender,
        client_id,
    )
    return True
