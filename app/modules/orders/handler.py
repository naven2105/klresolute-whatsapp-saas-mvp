from __future__ import annotations

"""
File: app/modules/orders/handler.py
Path: app/modules/orders/handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Orders module adapter.

Rules (LOCKED):
- Delegate ALL logic to existing Galitos order handler
- No new business logic here
- Return True if message was handled
"""

import logging
from sqlalchemy.orm import Session

from app.handlers.galitos_order_handler import handle_order  # EXISTING, STABLE

logger = logging.getLogger("module.orders")


def handle(
    *,
    db: Session,
    msg: dict,
    sender: str,
    business_msisdn: str,
) -> bool:
    """
    Orders module entry point.
    """

    try:
        handled = handle_order(
            db=db,
            sender=sender,
            msg=msg,
            business_msisdn=business_msisdn,
        )

        if handled:
            logger.info(
                "ORDERS_HANDLED | sender=%s | business=%s",
                sender,
                business_msisdn,
            )

        return bool(handled)

    except Exception:
        logger.exception(
            "ORDERS_HANDLER_FAIL | sender=%s | business=%s",
            sender,
            business_msisdn,
        )
        return True  # swallow to protect webhook
