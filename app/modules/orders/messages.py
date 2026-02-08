from __future__ import annotations

"""
File: app/modules/orders/messages.py
Path: app/modules/orders/messages.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Outbound messaging helpers for Orders module.

Rules (LOCKED):
- Messaging only
- No DB access
"""

import logging
from app.messaging.client_messenger import send_message

logger = logging.getLogger("module.orders.messages")


def send_food_menu(sender: str) -> None:
    send_message(
        to_number=sender,
        text=(
            "🍗 Galitos Food Menu\n\n"
            "1️⃣ 1/2 Chicken – R89\n"
            "2️⃣ Hot Box 3 Piece + Chips – R79\n"
            "3️⃣ Full Chicken – R159\n\n"
            "Reply with the number."
        ),
    )
    logger.info("ORDERS_MENU_SENT | sender=%s", sender)


def ask_for_flavour(sender: str) -> None:
    send_message(
        to_number=sender,
        text=(
            "Please choose a flavour:\n"
            "1. Lemon & Herb\n"
            "2. Mild\n"
            "3. Hot"
        ),
    )
    logger.info("ORDERS_FLAVOUR_PROMPT_SENT | sender=%s", sender)


def notify_staff(staff: list[str], order: dict) -> None:
    msg = (
        "📢 New Galitos Order\n\n"
        f"Item: {order.get('item_name')}\n"
        f"Flavour: {order.get('flavour')}\n"
        f"Total: R{order.get('total_amount')}\n"
        f"Customer: {order.get('customer_msisdn')}\n"
    )

    for msisdn in staff:
        try:
            send_message(to_number=msisdn, text=msg)
            logger.info(
                "ORDERS_STAFF_SENT | order_id=%s | staff=%s",
                order.get("id"),
                msisdn,
            )
        except Exception as exc:
            logger.exception(
                "ORDERS_STAFF_SEND_FAIL | order_id=%s | staff=%s | err=%s",
                order.get("id"),
                msisdn,
                exc,
            )
