from __future__ import annotations

"""
File: app/modules/join/handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Handle client opt-in (JOIN) logic.

Responsibilities:
- Detect JOIN command
- Create contact if new
- Send JOIN REQUEST / WELCOME messages from tables
- Return True if handled

Scope:
- Client-facing only
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.outbound.meta import MetaWhatsAppClient
from app.outbound.settings import load_meta_settings

logger = logging.getLogger("module.join")

_meta_client = MetaWhatsAppClient(settings=load_meta_settings())


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
    upper = body.upper()

    # ----------------------------------
    # Resolve client (INTEGER id)
    # ----------------------------------
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

    if not client_row:
        logger.error(
            "JOIN_CLIENT_NOT_FOUND | business=%s",
            business_msisdn,
        )
        return True

    client_id = client_row["klresolute_client_id"]

    # ----------------------------------
    # NON-JOIN → send JOIN REQUEST msg
    # ----------------------------------
    if upper != "JOIN":
        row = (
            db.execute(
                text(
                    """
                    SELECT message_text
                    FROM client_onboarding_messages
                    WHERE client_id = :client_id
                      AND message_key = 'join_request'
                      AND is_active = TRUE
                    LIMIT 1
                    """
                ),
                {"client_id": client_id},
            )
            .mappings()
            .first()
        )

        if row:
            _meta_client.send_session_message(
                to_msisdn=sender,
                text=row["message_text"],
            )

        return True

    # ----------------------------------
    # JOIN → persist contact
    # ----------------------------------
    try:
        exists = (
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

        if not exists:
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
        logger.exception(
            "JOIN_CONTACT_PERSIST_FAILED | sender=%s",
            sender,
        )
        return True

    # ----------------------------------
    # JOIN → send WELCOME msg
    # ----------------------------------
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

    if row:
        _meta_client.send_session_message(
            to_msisdn=sender,
            text=row["message_text"],
        )

    logger.info(
        "JOIN_COMPLETED | sender=%s | client_id=%s",
        sender,
        client_id,
    )

    return True
