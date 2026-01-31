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

from app.messaging.client_messenger import send_message

logger = logging.getLogger("module.join")


def handle(*, db: Session, msg: dict, sender: str, business_msisdn: str) -> bool:
    msg_type = msg.get("type")
    if msg_type != "text":
        return False

    body = msg.get("text", {}).get("body", "").strip()
    if body.upper() != "JOIN":
        return False

    # Resolve client
    client_row = (
        db.execute(
            text(
                """
                SELECT c.client_id
                FROM clients c
                JOIN whatsapp_numbers w ON w.client_id = c.client_id
                WHERE w.destination_number = :business
                LIMIT 1
                """
            ),
            {"business": business_msisdn},
        )
        .mappings()
        .first()
    )

    if not client_row:
        return True

    client_id = client_row["client_id"]

    # Check existing contact
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

    # Send response
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

    logger.info(
        "JOIN_HANDLED | sender=%s | client_id=%s | result=%s",
        sender,
        client_id,
        key,
    )
    return True
