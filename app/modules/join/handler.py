from __future__ import annotations

"""
File: app/modules/join/handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Handle client opt-in (JOIN) logic with DB-driven onboarding messages.

Responsibilities:
- Detect JOIN command
- Detect unknown sender pre-JOIN
- Read onboarding messages from client_onboarding_messages
- Create contact if new
- Send appropriate onboarding message
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
        return False

    body = msg.get("text", {}).get("body", "").strip()
    body_upper = body.upper()

    meta = get_meta_client()

    # ----------------------------------
    # Resolve client_id
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
        logger.exception(
            "JOIN_CLIENT_LOOKUP_FAILED | business=%s",
            business_msisdn,
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
    # Check existing contact
    # ----------------------------------
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

    # ----------------------------------
    # JOIN command
    # ----------------------------------
    if body_upper == "JOIN":
        if contact:
            msg_row = (
                db.execute(
                    text(
                        """
                        SELECT message_text
                        FROM client_onboarding_messages
                        WHERE client_id = :client_id
                          AND message_key = 'join_exists'
                          AND is_active = TRUE
                        LIMIT 1
                        """
                    ),
                    {"client_id": client_id},
                )
                .mappings()
                .first()
            )
        else:
            try:
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

            msg_row = (
                db.execute(
                    text(
                        """
                        SELECT message_text
                        FROM client_onboarding_messages
                        WHERE client_id = :client_id
                          AND message_key = 'join_success'
                          AND is_active = TRUE
                        LIMIT 1
                        """
                    ),
                    {"client_id": client_id},
                )
                .mappings()
                .first()
            )

        if msg_row:
            meta.send_session_message(
                to_msisdn=sender,
                text=msg_row["message_text"],
            )

        logger.info(
            "JOIN_COMPLETED | sender=%s",
            sender,
        )
        return True

    # ----------------------------------
    # Unknown sender (pre-JOIN)
    # ----------------------------------
    if not contact:
        msg_row = (
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

        if msg_row:
            meta.send_session_message(
                to_msisdn=sender,
                text=msg_row["message_text"],
            )

        logger.info(
            "JOIN_REQUEST_SENT | sender=%s",
            sender,
        )
        return True

    return False
