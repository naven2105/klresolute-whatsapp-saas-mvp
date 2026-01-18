"""
File: app/client/galitos_menu.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Galito’s customer food menu (Phase 1).

RULES (LOCKED):
- Customer-facing only
- Single-item orders only
- Starts an order conversation
- Writes ONLY to conversation_state
- Does NOT create orders
- Does NOT handle YES / NO
- Does NOT ask for confirmation
"""

from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.messaging.client_messenger import send_message


# ---------------------------------
# Phase 1: Hard-coded menu (safe)
# ---------------------------------
MENU_ITEMS = {
    "1": {
        "sku": "HB_3_CHIPS",
        "name": "Hot Box 3 Piece + Chips",
        "price": 79,
    },
    "2": {
        "sku": "QTR_CHICKEN_CHIPS",
        "name": "1/4 Chicken + Chips",
        "price": 59,
    },
    "3": {
        "sku": "HALF_CHICKEN",
        "name": "1/2 Chicken",
        "price": 89,
    },
}


def handle_galitos_menu(
    *,
    db: Session,
    sender_number: str,
    message_text: str,
    client_id: str,
) -> bool:
    """
    Entry point for Galito’s MENU flow.

    Returns:
        True  -> message handled here
        False -> not a Galito’s menu message
    """

    text_norm = message_text.strip().upper()

    # -------------------------------
    # SHOW MENU
    # -------------------------------
    if text_norm == "MENU":
        menu_lines = [
            "🍗 *Galito’s Menu* (Single item only)",
            "",
        ]

        for key, item in MENU_ITEMS.items():
            menu_lines.append(
                f"{key}. {item['name']} – R{item['price']}"
            )

        menu_lines.extend(
            [
                "",
                "Reply with the *number* to select.",
                "For multiple items, please call the store.",
            ]
        )

        send_message(sender_number, "\n".join(menu_lines))
        return True

    # -------------------------------
    # ITEM SELECTION
    # -------------------------------
    if text_norm in MENU_ITEMS:
        item = MENU_ITEMS[text_norm]

        # Close any previous active order state (safety)
        db.execute(
            text(
                """
                UPDATE conversation_state
                SET active = false,
                    completed_at = now()
                WHERE sender_msisdn = :sender
                  AND active = true
                  AND state_type = 'ORDER'
                """
            ),
            {"sender": sender_number},
        )

        # Create new conversation state (NO flavour yet)
        db.execute(
            text(
                """
                INSERT INTO conversation_state (
                    sender_msisdn,
                    client_id,
                    state_type,
                    order_pending,
                    item_sku,
                    item_name,
                    base_price,
                    drink_addon,
                    addon_price,
                    total_amount,
                    flavour,
                    active
                )
                VALUES (
                    :sender,
                    :client_id,
                    'ORDER',
                    true,
                    :item_sku,
                    :item_name,
                    :base_price,
                    'NONE',
                    0,
                    :total_amount,
                    NULL,
                    true
                )
                """
            ),
            {
                "sender": sender_number,
                "client_id": client_id,
                "item_sku": item["sku"],
                "item_name": item["name"],
                "base_price": item["price"],
                "total_amount": item["price"],
            },
        )

        db.commit()

        # Hand over to flavour selection
        send_message(
            sender_number,
            f"✅ *{item['name']}* selected\n"
            f"Price: R{item['price']}\n\n"
            "Choose flavour:\n"
            "1. Lemon & Herb\n"
            "2. Mild\n"
            "3. Hot"
        )

        return True

    return False
