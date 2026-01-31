from __future__ import annotations

"""
File: app/modules/join/handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Handle client opt-in (JOIN) logic.

Responsibilities:
- Detect JOIN command
- Create contact if new
- Respond using client_messages
- Return True if handled

Scope:
- Client-facing only
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.messaging.client_messenger import send_message

logger = logging.getLogger("module.join")


def handle(*, db: Session, msg: dict, sender: str, business_msisdn: str) -> bool:
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

    client_id = client_row["client_id"]

    # ----------------------------------
    # Contact lookup / creation
    # ----------------------------------
    try:
        contact = (
            db.execute(
                text(
                    """
                    SELECT contact_id
                    FROM contacts
                    WHERE contact_number = :sender
                    LIMIT 1
                    """
                ),
                {"sender": sender},
            )
            .first()
        )

        if contact:
            key = "join_exists"
        else:
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
            key = "join_success"

    except IntegrityError:
        db.rollback()
        logger.warning(
            "JOIN_CONTACT_RACE_CONDITION | sender=%s",
            sender,
        )
        key = "join_exists"

    except Exception:
        db.rollback()
        logger.error(
            "JOIN_CONTACT_PERSIST_FAILED | sender=%s",
            sender,
            exc_info=True,
        )
        return True

    # ----------------------------------
    # Message response
    # ----------------------------------
    try:
        msg_row = (
            db.execute(
                text(
                    """
                    SELECT cm.message_text
                    FROM client_messages cm
                    WHERE cm.client_id = :client_id
                      AND cm.message_key = :key
                      AND cm.is_active = TRUE
                    LIMIT 1
                    """
                ),
                {"client_id": client_id, "key": key},
            )
            .mappings()
            .first()
        )

        if msg_row:
            send_message(to_number=sender, text=msg_row["message_text"])
        else:
            logger.error(
                "JOIN_MESSAGE_MISSING | client_id=%s | key=%s",
                client_id,
                key,
            )

    except Exception:
        logger.error(
            "JOIN_RESPONSE_FAILED | sender=%s | client_id=%s",
            sender,
            client_id,
            exc_info=True,
        )

    logger.info(
        "JOIN_HANDLED | sender=%s | client_id=%s | result=%s",
        sender,
        client_id,
        key,
    )
    return True
