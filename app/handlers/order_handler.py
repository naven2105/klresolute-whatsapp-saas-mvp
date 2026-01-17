"""
File: app/handlers/order_handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Handle client single-item orders (Phase 1).

RULES (LOCKED):
- Client-facing only
- Single item per order
- No surveys
- No inspections
- No media
- Orders are confirmed only on explicit YES
- Prices are trusted (calculated upstream)
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Any

from sqlalchemy.orm import Session

from app.services.order_service import create_order, OrderCreate
from app.messaging.client_messenger import send_message


def handle_order_message(
    *,
    db: Session,
    from_number: str,
    text: str,
    context: Dict[str, Any],
) -> bool:
    """
    Entry point for order handling.

    Returns:
        True  -> message was handled here
        False -> not an order message, caller should continue routing
    """

    normalized = text.strip().upper()

    # =========================
    # CONFIRM ORDER
    # =========================
    if normalized == "YES" and context.get("order_pending") is True:
        order = OrderCreate(
            client_id=context["client_id"],
            customer_msisdn=from_number,

            item_sku=context["item_sku"],
            item_name=context["item_name"],
            flavour=context["flavour"],

            base_price=context["base_price"],
            drink_addon=context["drink_addon"],
            addon_price=context["addon_price"],

            total_amount=context["total_amount"],
            confirmed_at=datetime.utcnow(),
        )

        create_order(db, order)

        # Clear order state immediately
        context.clear()

        send_message(
            from_number,
            "✅ Thank you! Your order has been received.\n\n"
            "• This bot supports *single-item orders only*\n"
            "• For multiple items, please call the store\n\n"
            "Type MENU to order again."
        )

        return True

    # =========================
    # CANCEL ORDER
    # =========================
    if normalized == "NO" and context.get("order_pending") is True:
        context.clear()

        send_message(
            from_number,
            "❌ Order cancelled.\n\n"
            "Type MENU to start again."
        )

        return True

    # Not an order message
    return False
