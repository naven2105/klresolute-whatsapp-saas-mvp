"""
File: app/handlers/order_handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Handle client single-item orders (Phase 1) using DB-backed conversation state.

RULES (LOCKED):
- Client-facing only
- Single item per order
- Conversation state is stored in DB
- State is MARKED INACTIVE (not deleted) on completion
- Orders are confirmed only on explicit YES
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.services.order_service import create_order, OrderCreate
from app.messaging.client_messenger import send_message


def _get_active_order_state(db: Session, sender_msisdn: str) -> dict | None:
    row = db.execute(
        text(
            """
            SELECT *
            FROM conversation_state
            WHERE sender_msisdn = :sender
              AND active = true
              AND state_type = 'ORDER'
            ORDER BY started_at DESC
            LIMIT 1
            """
        ),
        {"sender": sender_msisdn},
    ).mappings().first()

    return dict(row) if row else None


def _close_order_state(db: Session, state_id: str) -> None:
    db.execute(
        text(
            """
            UPDATE conversation_state
            SET active = false,
                completed_at = now()
            WHERE id = :id
            """
        ),
        {"id": state_id},
    )
    db.commit()


def handle_order_message(
    *,
    db: Session,
    from_number: str,
    text: str,
    context: Dict[str, Any],  # kept for compatibility, NOT USED
) -> bool:
    """
    Entry point for order handling.

    Returns:
        True  -> message was handled here
        False -> not an order message
    """

    normalized = text.strip().upper()

    state = _get_active_order_state(db, from_number)
    if not state:
        return False

    # =========================
    # CONFIRM ORDER
    # =========================
    if normalized == "YES":
        order = OrderCreate(
            client_id=state["client_id"],
            customer_msisdn=from_number,

            item_sku=state["item_sku"],
            item_name=state["item_name"],
            flavour=state["flavour"],

            base_price=state["base_price"],
            drink_addon=state["drink_addon"],
            addon_price=state["addon_price"],

            total_amount=state["total_amount"],
            confirmed_at=datetime.utcnow(),
        )

        create_order(db, order)
        _close_order_state(db, state["id"])

        send_message(
            from_number,
            "✅ Thank you! Your order has been received.\n\n"
            "• Single-item orders only via bot\n"
            "• For multiple items, please call the store\n\n"
            "Type MENU to order again."
        )

        return True

    # =========================
    # CANCEL ORDER
    # =========================
    if normalized == "NO":
        _close_order_state(db, state["id"])

        send_message(
            from_number,
            "❌ Order cancelled.\n\n"
            "Type MENU to start again."
        )

        return True

    # Message not relevant to order
    return False
