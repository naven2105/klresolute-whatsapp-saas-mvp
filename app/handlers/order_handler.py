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
- Flavour MUST be selected by client
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.services.order_service import create_order, OrderCreate
from app.outbound.meta import MetaWhatsAppClient
from app.outbound.settings import load_meta_settings


_meta_client = MetaWhatsAppClient(settings=load_meta_settings())


def _send_text(to_number: str, text: str) -> None:
    _meta_client.send_session_message(
        to_msisdn=to_number,
        text=text,
    )


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


def _set_flavour(db: Session, state_id: str, flavour: str) -> None:
    db.execute(
        text(
            """
            UPDATE conversation_state
            SET flavour = :flavour
            WHERE id = :id
            """
        ),
        {"id": state_id, "flavour": flavour},
    )
    db.commit()


def handle_order_message(
    *,
    db: Session,
    from_number: str,
    text: str,
    context: Dict[str, Any],  # kept for compatibility
) -> bool:

    normalized = text.strip().upper()

    state = _get_active_order_state(db, from_number)
    if not state:
        return False

    # =========================
    # AWAIT FLAVOUR
    # =========================
    if state.get("flavour") is None:
        if normalized in ("1", "2", "3"):
            flavour_map = {
                "1": "L",  # Lemon & Herb
                "2": "M",  # Mild
                "3": "H",  # Hot
            }
            _set_flavour(db, state["id"], flavour_map[normalized])

            _send_text(
                from_number,
                f"✅ {state['item_name']}\n"
                f"Flavour selected.\n"
                f"Price: R{state['total_amount']}\n\n"
                "Reply YES to confirm\n"
                "Reply NO to cancel"
            )
            return True

        _send_text(
            from_number,
            "Choose flavour:\n"
            "1. Lemon & Herb\n"
            "2. Mild\n"
            "3. Hot"
        )
        return True

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

        _send_text(
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
        _send_text(
            from_number,
            "❌ Order cancelled.\n\n"
            "Type MENU to start again."
        )
        return True

    return True
