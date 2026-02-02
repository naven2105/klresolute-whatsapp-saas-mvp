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

    # -----------------------------
    # Guard: only text messages
    # -----------------------------
    if not msg or msg.get("type") != "text":
        return False

    try:
        handled = False

        # ----------------------------------
        # Delegate to legacy Galitos handler
        # ----------------------------------
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
            logger.error(
                "ORDERS_DELEGATE_MISSING | module=galitos_order_handler"
            )
            return False

        if handled:
            logger.info(
                "ORDERS_HANDLED | sender=%s | business=%s",
                sender,
                business_msisdn,
            )

        return bool(handled)

    except Exception as exc:
        # ----------------------------------
        # Guard: never break webhook
        # ----------------------------------
        logger.exception(
            "ORDERS_HANDLER_FAIL | sender=%s | business=%s | err=%s",
            sender,
            business_msisdn,
            exc,
        )
        try:
            db.rollback()
        except Exception:
            pass

        return True  # swallow to protect webhook
