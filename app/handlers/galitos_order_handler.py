from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.services.order_service import create_order, OrderCreate
from app.services.galitos_staff_notifier import notify_galitos_staff
from app.outbound.meta import MetaWhatsAppClient
from app.outbound.settings import load_meta_settings

logger = logging.getLogger("galitos_order_handler")

_meta_client = MetaWhatsAppClient(settings=load_meta_settings())

# safety: auto-expire orders after 10 minutes
ORDER_TIMEOUT_MINUTES = 10


def _send_text(to_number: str, message_text: str) -> None:
    logger.info("ORDER_SEND_TEXT | to=%s | text=%r", to_number, message_text)
    _meta_client.send_session_message(
        to_msisdn=to_number,
        text=message_text,
    )


def _close_order_state(db: Session, state_id: str, reason: str) -> None:
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
    logger.info("ORDER_STATE_CLOSED | state_id=%s | reason=%s", state_id, reason)


def handle_order_message(
    *,
    db: Session,
    from_number: str,
    message_text: str,
    context: Dict[str, Any],
) -> bool:

    logger.info(
        "ORDER_HANDLER_ENTER | sender=%s | text=%r",
        from_number,
        message_text,
    )

    state = db.execute(
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
        {"sender": from_number},
    ).mappings().first()

    if not state:
        return False

    # --- state timeout guard ---
    started_at = state.get("started_at")
    if started_at:
        now_utc = datetime.now(timezone.utc)
        if now_utc - started_at > timedelta(minutes=ORDER_TIMEOUT_MINUTES):
            _close_order_state(db, state["id"], "timeout")
            _send_text(from_number, "Your previous order expired. Type MENU to start again.")
            return True

    normalized = (message_text or "").strip().upper()

    # --- escape / cancel ---
    if normalized == "MENU":
        _close_order_state(db, state["id"], "menu_cancel")
        _send_text(from_number, "Order cancelled. Type MENU to start again.")
        return True

    if normalized == "NO":
        _close_order_state(db, state["id"], "user_cancel")
        _send_text(from_number, "Order cancelled. Type MENU to start again.")
        return True

    # --- flavour selection ---
    if state.get("flavour") is None:
        flavour_map = {
            "1": ("L", "Lemon & Herb"),
            "2": ("M", "Mild"),
            "3": ("H", "Hot"),
        }

        if normalized in flavour_map:
            flavour_code, flavour_label = flavour_map[normalized]
            db.execute(
                text(
                    """
                    UPDATE conversation_state
                    SET flavour = :flavour
                    WHERE id = :id
                    """
                ),
                {"id": state["id"], "flavour": flavour_code},
            )
            db.commit()

            _send_text(
                from_number,
                f"{state['item_name']}\n"
                f"Flavour: {flavour_label}\n"
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
            "3. Hot\n\n"
            "Or reply MENU to cancel."
        )
        return True

    # --- confirm ---
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
        )
        create_order(db, order)

        _close_order_state(db, state["id"], "confirmed")

        now = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=2)))
        timestamp = now.strftime("%A, %Y-%m-%d · %Hh%M")

        flavour_label = (
            "Hot" if state["flavour"] == "H"
            else "Mild" if state["flavour"] == "M"
            else "Lemon & Herb"
        )

        staff_message = (
            f"New Galitos Order | {timestamp} | "
            f"Item: {state['item_name']} | "
            f"Flavour: {flavour_label} | "
            f"Total: R{state['total_amount']} | "
            f"Customer: {from_number}"
        )

        # 🔴 PATCH: explicit proof this line is reached
        logger.info(
            "ORDER_STAFF_NOTIFY_CALLING | client_id=%s | state_id=%s",
            state["client_id"],
            state["id"],
        )

        notify_galitos_staff(
            db=db,
            client_id=state["client_id"],
            message=staff_message,
        )

        _send_text(from_number, "Thank you. Order received.")
        return True

    # --- fallback escape ---
    _send_text(
        from_number,
        "Reply YES to confirm, NO to cancel, or MENU to start again."
    )
    return True
