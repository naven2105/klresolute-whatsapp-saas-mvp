from __future__ import annotations

"""
File: app/handlers/galitos_order_handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Handle client single-item orders (Phase 1) using DB-backed conversation state.
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
    _meta_client.send_session_message(
        to_msisdn=to_number,
        text=text,
    )


# =======================================================
# Notify ALL active Galitos staff members of client order
# =======================================================

def _notify_galitos_staff(
    db: Session,
    *,
    client_id: int,   # ⚠️ MUST be INTEGER
    message: str,
) -> None:
    """
    Notify ALL active Galitos staff members.
    Uses galitos_staff.klresolute_client_id (INTEGER).
    """

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

    if not rows:
        logger.warning(
            "NO_GALITOS_STAFF_FOUND | client_id=%s",
            client_id,
        )
        return

    for r in rows:
        try:
            _meta_client.send_generic_business_update_template(
                to_msisdn=r.msisdn,
                blob_text=message,
            )
            logger.info(
                "STAFF_NOTIFIED | client_id=%s | msisdn=%s",
                client_id,
                r.msisdn,
            )
        except Exception:
            logger.exception(
                "STAFF_NOTIFY_FAIL | client_id=%s | msisdn=%s",
                client_id,
                r.msisdn,
            )


# =================================================
# Conversation helpers
# =================================================

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

    state = _get_active_order_state(db, from_number)
    if not state:
        return False

    normalized = (text or "").strip().upper()

    # -------------------------------
    # MENU = HARD RESET
    # -------------------------------
    if normalized == "MENU":
        _close_order_state(db, state["id"])
        _send_text(from_number, "Order cancelled.\n\nReply MENU to start again.")
        return True

    # -------------------------------
    # AWAIT FLAVOUR
    # -------------------------------
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

    # -------------------------------
    # CONFIRM ORDER
    # -------------------------------
    if normalized == "YES":
        order = OrderCreate(
            client_id=state["client_id"],  # INTEGER ✅
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

        staff_message = (
            f"Order | {state['item_name']} | "
            f"{state['flavour']} | "
            f"R{state['total_amount']} | "
            f"Cust: {from_number} | "
            f"{datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=2))).strftime('%Y-%m-%d %H:%M')}"
        )

        _notify_galitos_staff(
            db,
            client_id=state["client_id"],  # INTEGER ✅ FIX
            message=staff_message,
        )

        _send_text(
            from_number,
            "✅ Thank you! Your order has been received.\n\n"
            "Type MENU to order again."
        )
        return True

    # -------------------------------
    # CANCEL ORDER
    # -------------------------------
    if normalized == "NO":
        _close_order_state(db, state["id"])
        _send_text(from_number, "❌ Order cancelled.\n\nType MENU to start again.")
        return True

    _send_text(from_number, "Reply YES to confirm or NO to cancel.")
    return True  
