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

import app.handlers.galitos_order_handler as galitos_orders  # MODULE import (SAFE)

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
        # 🔒 Delegate to the existing handler's public entry point
        if hasattr(galitos_orders, "handle_order"):
            handled = galitos_orders.handle_order(
                db=db,
                sender=sender,
                msg=msg,
                business_msisdn=business_msisdn,
            )
        elif hasattr(galitos_orders, "handle"):
            handled = galitos_orders.handle(
                db=db,
                sender=sender,
                msg=msg,
                business_msisdn=business_msisdn,
            )
        else:
            logger.error("GALITOS_HANDLER_NO_ENTRYPOINT")
            return False

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
