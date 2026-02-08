from __future__ import annotations

"""
File: app/handlers/galitos_order_handler.py
Path: app/handlers/galitos_order_handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Handle Galitos single-item order lifecycle (Phase 1).

Responsibilities (LOCKED):
- Maintain conversation_state
- Confirm / cancel orders
- Persist confirmed orders
- Trigger staff notification
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.services.order_service import create_order, OrderCreate
from app.outbound.meta import MetaWhatsAppClient
from app.outbound.settings import load_meta_settings
from app.handlers.galitos_staff_notifier import notify_galitos_staff

logger = logging.getLogger("galitos.order.handler")

_meta_client = MetaWhatsAppClient(settings=load_meta_settings())


# -------------------------------------------------
# Messaging
# -------------------------------------------------

def _send_text(to_number: str, text: str) -> None:
    logger.info("SEND_TEXT | to=%s | len=%s", to_number, len(text))
    _meta_client.send_session_message(
        to_msisdn=to_number,
        text=text,
    )


# -------------------------------------------------
# Conversation helpers
# -------------------------------------------------

def _get_active_order_state(db: Session, sender: str) -> dict | None:
    try:
        row = (
            db.execute(
                text(
                    """
                    SELECT *
                    FROM conversation_state
                    WHERE sender_msisdn = :sender
                      AND active = TRUE
                      AND state_type = 'ORDER'
                    ORDER BY started_at DESC
                    LIMIT 1
                    """
                ),
                {"sender": sender},
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None
    except Exception:
        logger.exception(
            "ORDER_STATE_FETCH_FAIL | sender=%s",
            sender,
        )
        return None


def _close_order_state(db: Session, state_id: str) -> None:
    try:
        db.execute(
            text(
                """
                UPDATE conversation_state
                SET active = FALSE,
                    completed_at = now()
                WHERE id = :id
                """
            ),
            {"id": state_id},
        )
        db.commit()
        logger.info("ORDER_STATE_CLOSED | state_id=%s", state_id)
    except Exception:
        db.rollback()
        logger.exception(
            "ORDER_STATE_CLOSE_FAIL | state_id=%s",
            state_id,
        )


def _set_flavour(db: Session, state_id: str, flavour: str) -> None:
    try:
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
        logger.info(
            "ORDER_FLAVOUR_SET | state_id=%s | flavour=%s",
            state_id,
            flavour,
        )
    except Exception:
        db.rollback()
        logger.exception(
            "ORDER_FLAVOUR_SET_FAIL | state_id=%s | flavour=%s",
            state_id,
            flavour,
        )


# -------------------------------------------------
# Main handler
# -------------------------------------------------

def handle_order_message(
    *,
    db: Session,
    from_number: str,
    text: str,
    context: Dict[str, Any],
) -> bool:

    logger.info(
        "ORDER_HANDLER_ENTER | sender=%s | text=%r",
        from_number,
        text,
    )

    state = _get_active_order_state(db, from_number)
    if not state:
        logger.info(
            "ORDER_HANDLER_NO_ACTIVE_STATE | sender=%s",
            from_number,
        )
        return False

    normalized = (text or "").strip().upper()

    if normalized == "MENU":
        _close_order_state(db, state["id"])
        _send_text(from_number, "Order cancelled.\n\nReply MENU to start again.")
        return True

    if state.get("flavour") is None:
        flavour_map = {
            "1": ("L", "Lemon & Herb"),
            "2": ("M", "Mild"),
            "3": ("H", "Hot"),
        }

        if normalized in flavour_map:
            code, label = flavour_map[normalized]
            _set_flavour(db, state["id"], code)

            _send_text(
                from_number,
                f"✅ {state['item_name']}\n"
                f"Flavour: {label}\n"
                f"Price: R{state['total_amount']}\n\n"
                "Reply YES to confirm\n"
                "Reply NO to cancel"
            )
            return True

        _send_text(
            from_number,
            "Please choose a flavour:\n"
            "1. Lemon & Herb\n"
            "2. Mild\n"
            "3. Hot"
        )
        return True

    if normalized == "YES":
        try:
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
            logger.info(
                "ORDER_PERSISTED | sender=%s | client_id=%s",
                from_number,
                state["client_id"],
            )
        except Exception:
            logger.exception(
                "ORDER_CREATE_FAIL | sender=%s | client_id=%s",
                from_number,
                state.get("client_id"),
            )
            return True

        _close_order_state(db, state["id"])

        ts = (
            datetime.now(timezone.utc)
            .astimezone(timezone(timedelta(hours=2)))
            .strftime("%A, %Y-%m-%d · %Hh%M")
        )

        flavour_label = (
            "Hot" if state["flavour"] == "H"
            else "Mild" if state["flavour"] == "M"
            else "Lemon & Herb"
        )

        staff_message = (
            f"New Galitos Order | {ts} | "
            f"Item: {state['item_name']} | "
            f"Flavour: {flavour_label} | "
            f"Total: R{state['total_amount']} | "
            f"Customer: {from_number}"
        )

        notify_galitos_staff(
            db=db,
            client_id=state["client_id"],
            message=staff_message,
        )

        _send_text(
            from_number,
            "✅ Thank you! Your order has been received.\n\n"
            "Type MENU to order again."
        )
        return True

    if normalized == "NO":
        _close_order_state(db, state["id"])
        _send_text(from_number, "❌ Order cancelled.\n\nType MENU to start again.")
        return True

    _send_text(from_number, "Reply YES to confirm or NO to cancel.")
    return True
