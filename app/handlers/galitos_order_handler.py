from __future__ import annotations

"""
File: app/handlers/galitos_order_handler.py
Path: app/handlers/galitos_order_handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Handle client single-item orders (Phase 1) using DB-backed conversation state.

Rules (LOCKED):
- No schema changes
- No flow changes
- Add guards + logs only
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.services.order_service import create_order, OrderCreate
from app.outbound.meta import MetaWhatsAppClient
from app.outbound.settings import load_meta_settings

logger = logging.getLogger("galitos_order_handler")

_meta_client = MetaWhatsAppClient(settings=load_meta_settings())


# =================================================
# Messaging helpers
# =================================================

def _send_text(to_number: str, text: str) -> None:
    logger.info("ORDER_SEND_TEXT | to=%s | text=%r", to_number, text)
    _meta_client.send_session_message(
        to_msisdn=to_number,
        text=text,
    )


# =================================================
# Staff notification
# =================================================

def _notify_galitos_staff(
    db: Session,
    *,
    client_id: int,
    message: str,
) -> None:
    logger.info(
        "ORDER_STAFF_NOTIFY_ENTER | client_id=%s | message=%r",
        client_id,
        message,
    )

    try:
        rows = db.execute(
            text(
                """
                SELECT msisdn
                FROM galitos_staff
                WHERE klresolute_client_id = :client_id
                  AND is_active = true
                """
            ),
            {"client_id": client_id},
        ).fetchall()
    except Exception:
        logger.exception(
            "ORDER_STAFF_NOTIFY_QUERY_FAIL | client_id=%s",
            client_id,
        )
        return

    logger.info(
        "ORDER_STAFF_NOTIFY_ROWS | client_id=%s | count=%s",
        client_id,
        len(rows),
    )

    if not rows:
        logger.error(
            "ORDER_STAFF_NOTIFY_ABORTED | reason=no_active_staff | client_id=%s",
            client_id,
        )
        return

    for r in rows:
        try:
            logger.info(
                "ORDER_STAFF_NOTIFY_SEND | client_id=%s | msisdn=%s",
                client_id,
                r.msisdn,
            )

            _meta_client.send_generic_business_update_template(
                to_msisdn=r.msisdn,
                blob_text=message,
            )

            logger.info(
                "ORDER_STAFF_NOTIFY_SENT | client_id=%s | msisdn=%s",
                client_id,
                r.msisdn,
            )
        except Exception:
            logger.exception(
                "ORDER_STAFF_NOTIFY_SEND_FAIL | client_id=%s | msisdn=%s",
                client_id,
                r.msisdn,
            )


# =================================================
# Conversation helpers
# =================================================

def _get_active_order_state(db: Session, sender_msisdn: str) -> dict | None:
    try:
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

        if not row:
            logger.info(
                "ORDER_STATE_NONE | sender=%s",
                sender_msisdn,
            )
            return None

        logger.info(
            "ORDER_STATE_FOUND | sender=%s | state_id=%s | flavour=%s",
            sender_msisdn,
            row.get("id"),
            row.get("flavour"),
        )
        return dict(row)

    except Exception:
        logger.exception(
            "ORDER_STATE_FETCH_FAIL | sender=%s",
            sender_msisdn,
        )
        return None


def _close_order_state(db: Session, state_id: str) -> None:
    try:
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


# =================================================
# Main handler
# =================================================

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
            "ORDER_HANDLER_EXIT | reason=no_active_state | sender=%s",
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
            flavour_code, flavour_label = flavour_map[normalized]
            _set_flavour(db, state["id"], flavour_code)

            _send_text(
                from_number,
                f"✅ {state['item_name']}\n"
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
            "3. Hot"
        )
        return True

    if normalized == "YES":
        logger.info(
            "ORDER_CONFIRM_ENTER | sender=%s | state_id=%s | client_id=%s",
            from_number,
            state["id"],
            state.get("client_id"),
        )

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

        _notify_galitos_staff(
            db,
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
