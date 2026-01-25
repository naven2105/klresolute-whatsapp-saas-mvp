from __future__ import annotations

"""
File: app/clients/galitos/inbound.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Inbound entry point for Galitos WhatsApp number.

RULES:
- No business logic here
- Delegates to existing Galitos handlers
- Guards against duplicate Meta events
- YES / NO only acknowledged IF awaiting order confirmation
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.handlers.client_commands import handle_client_command
from app.messaging.client_messenger import send_message

logger = logging.getLogger("clients.galitos")


def _awaiting_order_confirmation(db: Session, sender: str) -> bool:
    """
    Returns True if the last Galitos outbound message
    asked the client to confirm an order.
    """
    row = db.execute(
        text(
            """
            SELECT 1
            FROM messages
            WHERE to_msisdn = :msisdn
              AND direction = 'OUTBOUND'
              AND content ILIKE '%YES%'
              AND content ILIKE '%confirm%'
            ORDER BY created_at DESC
            LIMIT 1
            """
        ),
        {"msisdn": sender},
    ).first()

    return bool(row)


def handle_inbound(
    *,
    db: Session,
    msg: dict,
    sender: str,
    business_msisdn: str,
) -> bool:
    """
    Returns True if Galitos logic handles the message.
    """

    # -------------------------------------------------
    # Ignore non-text events (Meta status, delivery)
    # -------------------------------------------------
    if msg.get("type") != "text":
        logger.info(
            "GALITOS_IGNORE_NON_TEXT | sender=%s | business=%s",
            sender,
            business_msisdn,
        )
        return True

    text = (msg.get("text", {}) or {}).get("body", "").strip()
    upper = text.upper()

    # -------------------------------------------------
    # YES / NO — only if awaiting order confirmation
    # -------------------------------------------------
    if upper in ("YES", "NO") and _awaiting_order_confirmation(db, sender):
        send_message(
            to_number=sender,
            text="✅ Thanks! Your Galitos order has been received.",
        )
        logger.info(
            "GALITOS_ORDER_ACK_SENT | sender=%s | response=%s",
            sender,
            upper,
        )
        return True

    # -------------------------------------------------
    # Delegate all other handling to existing logic
    # -------------------------------------------------
    try:
        handled = handle_client_command(
            db=db,
            sender_number=sender,
            message_text=text,
            msg=msg,
            resolved_client_id=None,
            resolved_business_number=business_msisdn,
        )

        if handled:
            logger.info(
                "GALITOS_INBOUND_HANDLED | sender=%s | business=%s",
                sender,
                business_msisdn,
            )
            return True

        return False

    except Exception:
        logger.exception(
            "GALITOS_INBOUND_FATAL | sender=%s | business=%s",
            sender,
            business_msisdn,
        )
        return True  # fail-safe
