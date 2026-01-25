from __future__ import annotations

"""
File: app/clients/galitos/inbound.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Inbound entry point for Galitos WhatsApp number.

RULES:
- NO business logic here
- Text + interactive messages must pass through
- YES / NO intercepted ONLY when awaiting order confirmation
- Status / delivery events ignored
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.handlers.client_commands import handle_client_command
from app.messaging.client_messenger import send_message

logger = logging.getLogger("clients.galitos")


def _awaiting_order_confirmation(db: Session, sender: str) -> bool:
    row = db.execute(
        text(
            """
            SELECT 1
            FROM messages
            WHERE to_msisdn = :msisdn
              AND direction = 'OUTBOUND'
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

    msg_type = msg.get("type")

    # ----------------------------------
    # Ignore Meta status / delivery events ONLY
    # ----------------------------------
    if msg_type not in ("text", "interactive"):
        logger.info(
            "GALITOS_IGNORE_EVENT | type=%s | sender=%s",
            msg_type,
            sender,
        )
        return True

    # ----------------------------------
    # YES / NO — text only, awaiting confirmation
    # ----------------------------------
    if msg_type == "text":
        text_body = (msg.get("text", {}) or {}).get("body", "").strip()
        upper = text_body.upper()

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

    # ----------------------------------
    # EVERYTHING ELSE MUST PASS THROUGH
    # (including interactive flavour selection)
    # ----------------------------------
    try:
        handled = handle_client_command(
            db=db,
            sender_number=sender,
            message_text=(
                (msg.get("text", {}) or {}).get("body", "")
                if msg_type == "text"
                else ""
            ),
            msg=msg,
            resolved_client_id=None,
            resolved_business_number=business_msisdn,
        )

        if handled:
            logger.info(
                "GALITOS_INBOUND_HANDLED | sender=%s | type=%s",
                sender,
                msg_type,
            )
            return True

        return False

    except Exception:
        logger.exception("GALITOS_INBOUND_FATAL | sender=%s", sender)
        return True
