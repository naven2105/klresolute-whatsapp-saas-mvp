from __future__ import annotations

"""
File: app/modules/join/handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Handle client opt-in (JOIN) logic.

Responsibilities:
- Detect JOIN command
- Create contact if new
- Send JOIN welcome message (from DB)
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

    logger.info(
        "JOIN_COMMAND_DETECTED | sender=%s | business=%s",
        sender,
        business_msisdn,
    )

    # ----------------------------------
    # Resolve client via whatsapp_numbers (INTEGER client_id)
    # ----------------------------------
    try:
        client_row = (
            db.execute(
                text(
                    """
                    SELECT klresolute_client_id AS client_id
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

    client_id = client_row.get("client_id")

    # ----------------------------------
    # Fetch onboarding messages (join_welcome / join_exists)
    # ----------------------------------
    join_welcome_text = None
    join_exists_text = None

    try:
        row = (
            db.execute(
                text(
                    """
                    SELECT message_key, message_text
                    FROM client_onboarding_messages
                    WHERE client_id = :client_id
                      AND message_key IN ('join_welcome', 'join_exists')
                      AND is_active = TRUE
                    """
                ),
                {"client_id": client_id},
            )
            .mappings()
            .all()
        )

        for r in row:
            if r.get("message_key") == "join_welcome":
                join_welcome_text = r.get("message_text")
            if r.get("message_key") == "join_exists":
                join_exists_text = r.get("message_text")

    except Exception:
        logger.error(
            "JOIN_ONBOARDING_MESSAGE_FETCH_FAIL | client_id=%s",
            client_id,
            exc_info=True,
        )

    if not join_welcome_text:
        join_welcome_text = "✅ You are now subscribed."

    if not join_exists_text:
        join_exists_text = "✅ You are already subscribed."

    # ----------------------------------
    # Contact lookup / creation (client_contacts)
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
                      AND is_opted_out = FALSE
                    LIMIT 1
                    """
                ),
                {"client_id": client_id, "sender": sender},
            )
            .first()
        )

        if existing:
            send_message(to_number=sender, text=join_exists_text)
            logger.info(
                "JOIN_WELCOME_SENT | sender=%s | client_id=%s | kind=exists",
                sender,
                client_id,
            )
            return True

        db.execute(
            text(
                """
                INSERT INTO client_contacts (client_id, contact_number, is_opted_out)
                VALUES (:client_id, :sender, FALSE)
                ON CONFLICT DO NOTHING
                """
            ),
            {"client_id": client_id, "sender": sender},
        )
        db.commit()

        send_message(to_number=sender, text=join_welcome_text)
        logger.info(
            "JOIN_WELCOME_SENT | sender=%s | client_id=%s | kind=welcome",
            sender,
            client_id,
        )
        return True

    except IntegrityError:
        db.rollback()
        logger.warning(
            "JOIN_CONTACT_RACE_CONDITION | sender=%s | client_id=%s",
            sender,
            client_id,
        )
        send_message(to_number=sender, text=join_exists_text)
        logger.info(
            "JOIN_WELCOME_SENT | sender=%s | client_id=%s | kind=exists",
            sender,
            client_id,
        )
        return True

    except Exception:
        db.rollback()
        logger.error(
            "JOIN_CONTACT_PERSIST_FAILED | sender=%s | client_id=%s",
            sender,
            client_id,
            exc_info=True,
        )
        return True
