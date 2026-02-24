from __future__ import annotations

"""
File: app/handlers/galitos_order_handler.py
Path: app/handlers/galitos_order_handler.py
Project: KLResolute WhatsApp SaaS MVP

Sprint: Full UUID Identity Migration Hardening

Purpose:
Handle in-flight Galitos order conversation state and confirmation.

Guards / Enhancements (Sprint scope):
- Defensive db.rollback() to prevent aborted transaction cascades
- Extra logs for state progression and notify boundary
- No behaviour changes to order flow
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.services.order_service import create_order, OrderCreate
from app.clients.galitos.services.galitos_staff_notifier import notify_galitos_staff
from app.messaging.client_messenger import send_message

logger = logging.getLogger("galitos_order_handler")

# safety: auto-expire orders after 10 minutes
ORDER_TIMEOUT_MINUTES = 10


def _send_text(*, db: Session, business_msisdn: str, to_number: str, message_text: str) -> None:
    logger.info("ORDER_SEND_TEXT | to=%s | text=%r", to_number, message_text)

    if not business_msisdn:
        logger.error("ORDER_SEND_TEXT_SKIP | reason=missing_business_msisdn | to=%s", to_number)
        return

    # Defensive: clear aborted transaction before outbound settings lookup
    try:
        db.rollback()
        logger.info("ORDER_SEND_TEXT_DB_RESET | business=%s | to=%s", business_msisdn, to_number)
    except Exception:
        logger.exception("ORDER_SEND_TEXT_DB_RESET_FAIL | business=%s | to=%s", business_msisdn, to_number)

    try:
        send_message(
            db=db,
            business_msisdn=business_msisdn,
            to_number=to_number,
            text=message_text,
        )
    except Exception:
        logger.exception("ORDER_SEND_TEXT_FAIL | to=%s", to_number)


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

    # Defensive: if earlier SQL in the request failed, clear it first.
    try:
        db.rollback()
        logger.info("ORDER_HANDLER_DB_RESET | sender=%s", from_number)
    except Exception:
        logger.exception("ORDER_HANDLER_DB_RESET_FAIL | sender=%s", from_number)

    business_msisdn = (context or {}).get("business_msisdn")

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
        logger.info("ORDER_NO_ACTIVE_STATE | sender=%s", from_number)
        return False

    # --- state timeout guard ---
    started_at = state.get("started_at")
    if started_at:
        now_utc = datetime.now(timezone.utc)
        if now_utc - started_at > timedelta(minutes=ORDER_TIMEOUT_MINUTES):
            _close_order_state(db, state["id"], "timeout")
            _send_text(
                db=db,
                business_msisdn=business_msisdn,
                to_number=from_number,
                message_text="Your previous order expired. Type MENU to start again.",
            )
            return True

    normalized = (message_text or "").strip().upper()

    # --- escape / cancel ---
    if normalized == "MENU":
        _close_order_state(db, state["id"], "menu_cancel")
        _send_text(
            db=db,
            business_msisdn=business_msisdn,
            to_number=from_number,
            message_text="Order cancelled. Type MENU to start again.",
        )
        return True

    if normalized == "NO":
        _close_order_state(db, state["id"], "user_cancel")
        _send_text(
            db=db,
            business_msisdn=business_msisdn,
            to_number=from_number,
            message_text="Order cancelled. Type MENU to start again.",
        )
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
                db=db,
                business_msisdn=business_msisdn,
                to_number=from_number,
                message_text=(
                    f"{state['item_name']}\n"
                    f"Flavour: {flavour_label}\n"
                    f"Price: R{state['total_amount']}\n\n"
                    "Reply YES to confirm\n"
                    "Reply NO to cancel"
                ),
            )
            return True

        _send_text(
            db=db,
            business_msisdn=business_msisdn,
            to_number=from_number,
            message_text=(
                "Please choose a flavour:\n"
                "1. Lemon & Herb\n"
                "2. Mild\n"
                "3. Hot\n\n"
                "Or reply MENU to cancel."
            ),
        )
        return True

    # --- confirm ---
    if normalized == "YES":
        logger.info(
            "ORDER_CONFIRM_RECEIVED | sender=%s | state_id=%s | client_id=%s",
            from_number,
            state.get("id"),
            state.get("client_id"),
        )

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

        logger.info(
            "ORDER_STAFF_NOTIFY_CALLING | client_id=%s | state_id=%s",
            state["client_id"],
            state["id"],
        )

        # Defensive: clear transaction state before notifier DB reads
        try:
            db.rollback()
            logger.info("ORDER_NOTIFY_DB_RESET | client_id=%s", state.get("client_id"))
        except Exception:
            logger.exception("ORDER_NOTIFY_DB_RESET_FAIL | client_id=%s", state.get("client_id"))

        notify_galitos_staff(
            db=db,
            client_id=state["client_id"],
            message=staff_message,
        )

        _send_text(
            db=db,
            business_msisdn=business_msisdn,
            to_number=from_number,
            message_text="Thank you. Order received.",
        )
        return True

    # --- fallback escape ---
    _send_text(
        db=db,
        business_msisdn=business_msisdn,
        to_number=from_number,
        message_text="Reply YES to confirm, NO to cancel, or MENU to start again.",
    )
    return True
