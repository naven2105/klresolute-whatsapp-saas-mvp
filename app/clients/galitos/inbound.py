from __future__ import annotations

"""
File: app/clients/galitos/inbound.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Inbound router for Galitos WhatsApp number.

LOCKED RULES:
- DO NOT confirm orders here
- YES / NO confirmation is handled ONLY by galitos_order_handler
- This file only routes messages
"""

import logging
from sqlalchemy.orm import Session

from app.handlers.galitos_order_handler import handle_order_message

logger = logging.getLogger("clients.galitos")

GALITOS_BUSINESS_MSISDN = "27735534607"


def handle_inbound(
    *,
    db: Session,
    business_msisdn: str | None,
    sender: str,
    msg: dict,
) -> bool:
    """
    Returns True if handled, False otherwise.
    """

    if business_msisdn != GALITOS_BUSINESS_MSISDN:
        return False

    if msg.get("type") != "text":
        return False

    text = (msg.get("text", {}) or {}).get("body", "") or ""
    normalized = text.strip()

    # -------------------------------------------------
    # Delegate ALL order-related input to order handler
    # -------------------------------------------------
    handled = handle_order_message(
        db=db,
        from_number=sender,
        text=normalized,
        context={"client": "galitos"},
    )

    if handled:
        logger.info(
            "GALITOS_ORDER_HANDLER_USED | sender=%s | text=%r",
            sender,
            normalized,
        )
        return True

    # -------------------------------------------------
    # Not an order → let client_commands handle menus
    # -------------------------------------------------
    return False
