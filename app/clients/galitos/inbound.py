from __future__ import annotations

"""
File: app/clients/galitos/inbound.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Inbound router for Galitos WhatsApp number.

RULES (LOCKED):
- Orders are handled ONLY by galitos_order_handler
- Non-order text must fall through to client_commands
- This handler must CLAIM the message if it sends anything
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.handlers.galitos_order_handler import handle_order_message
from app.handlers.client_commands import handle_client_command as client_commands

logger = logging.getLogger("clients.galitos")

GALITOS_BUSINESS_MSISDN = "27735534607"


def _get_galitos_client_id(db: Session) -> int | None:
    row = db.execute(
        text(
            """
            SELECT id
            FROM klresolute_client
            WHERE LOWER(name) = 'galitos'
              AND is_active = TRUE
            LIMIT 1
            """
        )
    ).mappings().first()

    return row["id"] if row else None


def handle_inbound(
    *,
    db: Session,
    business_msisdn: str | None,
    sender: str,
    msg: dict,
) -> bool:

    if business_msisdn != GALITOS_BUSINESS_MSISDN:
        return False

    if msg.get("type") != "text":
        return False

    text = (msg.get("text", {}) or {}).get("body", "") or ""

    # -------------------------------------------------
    # Resolve Galitos client ID ONCE
    # -------------------------------------------------
    galitos_client_id = _get_galitos_client_id(db)

    # -------------------------------------------------
    # 1) ORDER FLOW (state-driven)
    # -------------------------------------------------
    if handle_order_message(
        db=db,
        from_number=sender,
        text=text,
        context={
            "client": "galitos",
            "kl_client_id": galitos_client_id,
        },
    ):
        logger.info(
            "GALITOS_ORDER_HANDLER_USED | sender=%s | text=%r",
            sender,
            text,
        )
        return True

    # -------------------------------------------------
    # 2) NON-ORDER → CUSTOMER MENU / HELP / FOOD
    # -------------------------------------------------
    handled = client_commands(
        db=db,
        sender_number=sender,
        message_text=text,
        msg=msg,
        resolved_client_id=galitos_client_id,
        resolved_business_number=business_msisdn,
    )

    return bool(handled)
