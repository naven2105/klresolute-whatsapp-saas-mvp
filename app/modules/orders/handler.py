from __future__ import annotations

"""
File: app/modules/orders/handler.py
Path: app/modules/orders/handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Orders module entry point.

Rules (LOCKED):
- Routing only
- No SQL except INSERT
- Delegate continuation to galitos_order_handler
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.handlers import galitos_order_handler as galitos_orders
from app.modules.orders.db import (
    get_active_order_state,
    get_klresolute_client_id,
    get_active_staff_numbers,
)
from app.modules.orders.messages import (
    send_food_menu,
    ask_for_flavour,
    notify_staff,
)

logger = logging.getLogger("module.orders")


def handle(
    *,
    db: Session,
    msg: dict,
    sender: str,
    business_msisdn: str,
) -> bool:

    logger.info(
        "ORDERS_MODULE_ENTER | sender=%s | business=%s | msg_type=%s",
        sender,
        business_msisdn,
        msg.get("type"),
    )

    if msg.get("type") != "text":
        return False

    body = ((msg.get("text") or {}).get("body") or "").strip()
    if not body:
        return False

    upper = body.upper()
    logger.info("ORDERS_TEXT | sender=%s | text=%s", sender, upper)

    try:
        active = get_active_order_state(db, sender)

        if active:
            galitos_orders.handle_order_message(
                db=db,
                from_number=sender,
                message_text=body,
                context={"business_msisdn": business_msisdn},
            )
            return True

        if upper in ("ORDER", "FOOD"):
            send_food_menu(
                db=db,
                business_msisdn=business_msisdn,
                sender=sender,
            )
            return True

        if body.isdigit():
            menu = {
                "1": ("HALF_CHICKEN", "1/2 Chicken", 89),
                "2": ("HB_3_CHIPS", "Hot Box 3 Piece + Chips", 79),
                "3": ("FULL_CHICKEN", "Full Chicken", 159),
            }

            if body not in menu:
                logger.info(
                    "ORDERS_INVALID_SELECTION | sender=%s | value=%s",
                    sender,
                    body,
                )
                return False

            client_id = get_klresolute_client_id(db, business_msisdn)
            if client_id is None:
                return True

            sku, name, price = menu[body]

            db.execute(
                text(
                    """
                    INSERT INTO conversation_state (
                        sender_msisdn,
                        client_id,
                        state_type,
                        item_sku,
                        item_name,
                        base_price,
                        drink_addon,
                        addon_price,
                        total_amount,
                        active
                    )
                    VALUES (
                        :sender,
                        :client_id,
                        'ORDER',
                        :sku,
                        :name,
                        :price,
                        'NONE',
                        0,
                        :price,
                        true
                    )
                    """
                ),
                {
                    "sender": sender,
                    "client_id": client_id,
                    "sku": sku,
                    "name": name,
                    "price": price,
                },
            )
            db.commit()

            logger.info(
                "ORDERS_STATE_CREATED | sender=%s | item=%s",
                sender,
                name,
            )

            ask_for_flavour(
                db=db,
                business_msisdn=business_msisdn,
                sender=sender,
            )
            return True

        return False

    except IntegrityError:
        db.rollback()
        logger.warning("ORDERS_INTEGRITY_RECOVERED | sender=%s", sender)
        ask_for_flavour(
            db=db,
            business_msisdn=business_msisdn,
            sender=sender,
        )
        return True

    except Exception:
        db.rollback()
        logger.exception(
            "ORDERS_HANDLER_FATAL | sender=%s | business=%s",
            sender,
            business_msisdn,
        )
        return True
