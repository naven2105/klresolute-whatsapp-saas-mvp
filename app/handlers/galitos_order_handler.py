from __future__ import annotations

"""
File: app/handlers/galitos_order_handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Handle client single-item orders (Phase 1) using DB-backed conversation state.

RULES (LOCKED):
- Client-facing only
- Single item per order
- Conversation state is stored in DB
- State is MARKED INACTIVE (not deleted) on completion
- Orders are confirmed only on explicit YES
- MENU always resets the conversation
- Unknown input = guidance, not cancellation
- If ORDER state is active, this handler ALWAYS consumes input
"""

import logging
from datetime import datetime
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
    logger.info("SEND_TEXT | to=%s | text=%r", to_number, text)
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
    client_id: int,
    message: str,
) -> None:
    """
    Notify ALL active Galitos staff members for a client.
    """
    logger.info(
        "STAFF_NOTIFY_BEGIN | client_id=%s",
        client_id,
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

        logger.info(
            "STAFF_COUNT | client_id=%s | count=%s",
            client_id,
            len(rows),
        )

        for r in rows:
            try:
                _meta_client.send_template_message(
                    to_msisdn=r.msisdn,
                    template_name="klr_notification_v1",
                    language="en_US",
                    components=[
                        {
                            "type": "body",
                            "parameters": [
                                {"type": "text", "text": message}
                            ],
                        }
                    ],
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

    except Exception:
        logger.exception(
            "STAFF_NOTIFY_FATAL | client_id=%s",
            client_id,
        )


# =================================================
# Conversation helpers
# =================================================

def _get_active_order_state(db: Session, sender_msisdn: str) -> dict | None:
    logger.info("FETCH_ORDER_STATE | sender=%s", sender_msisdn)
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
        logger.info("NO_ACTIVE_ORDER_STATE | sender=%s", sender_msisdn)
        return None

    logger.info(
        "ACTIVE_ORDER_STATE_FOUND | sender=%s | state_id=%s",
        sender_msisdn,
        row["id"],
    )
    return dict(row)


def _close_order_state(db: Session, state_id: str) -> None:
    logger.info("CLOSE_ORDER_STATE | state_id=%s", state_id)
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
    logger.info("SET_FLAVOUR | state_id=%s | flavour=%s", state_id, flavour)
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
    """
    Entry point for order handling.
    """

    logger.info(
        "ENTER | sender=%s | text=%r | context=%s",
        from_number,
        text,
        context,
    )

    try:
        state = _get_active_order_state(db, from_number)
        if not state:
            logger.info("EXIT | no active order | sender=%s", from_number)
            return False

        normalized = (text or "").strip().upper()
        logger.info(
            "ORDER_STATE_ACTIVE | sender=%s | input=%s",
            from_number,
            normalized,
        )

        # -------------------------------
        # MENU = HARD RESET
        # -------------------------------
        if normalized == "MENU":
            _close_order_state(db, state["id"])
            _send_text(
                from_number,
                "Order cancelled.\n\n"
                "Please reply MENU to start again."
            )
            logger.info("ORDER_RESET_BY_MENU | sender=%s", from_number)
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

                logger.info(
                    "FLAVOUR_SELECTED | sender=%s | flavour=%s",
                    from_number,
                    flavour_label,
                )
                return True

            _send_text(
                from_number,
                "Please choose a flavour:\n"
                "1. Lemon & Herb\n"
                "2. Mild\n"
                "3. Hot\n\n"
                "Reply MENU to start again."
            )

            logger.warning(
                "INVALID_FLAVOUR_INPUT | sender=%s | input=%s",
                from_number,
                normalized,
            )
            return True

        # -------------------------------
        # CONFIRM ORDER
        # -------------------------------
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

            # -------------------------------
            # Notify Galitos staff
            # -------------------------------
            staff_message = (
                f"Order | {state['item_name']} | "
                f"{state['flavour']} | "
                f"R{state['total_amount']} | "
                f"Cust: {from_number} | "
                f"{datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )

            _notify_galitos_staff(
                db,
                client_id=state["client_id"],
                message=staff_message,
            )

            _send_text(
                from_number,
                "✅ Thank you! Your order has been received.\n\n"
                "• Single-item orders only via bot\n"
                "• For multiple items, please call the store\n\n"
                "Type MENU to order again."
            )

            logger.info(
                "ORDER_CONFIRMED | sender=%s | staff_notified=true",
                from_number,
            )
            return True

        # -------------------------------
        # CANCEL ORDER
        # -------------------------------
        if normalized == "NO":
            _close_order_state(db, state["id"])
            _send_text(
                from_number,
                "❌ Order cancelled.\n\n"
                "Type MENU to start again."
            )

            logger.info("ORDER_CANCELLED_BY_USER | sender=%s", from_number)
            return True

        # -------------------------------
        # UNKNOWN INPUT
        # -------------------------------
        _send_text(
            from_number,
            "Please reply YES to confirm or NO to cancel.\n"
            "Reply MENU to start again."
        )

        logger.warning(
            "UNKNOWN_ORDER_INPUT | sender=%s | input=%s",
            from_number,
            normalized,
        )
        return True

    except Exception:
        logger.exception(
            "ERROR | galitos_order_handler | sender=%s | text=%r",
            from_number,
            text,
        )
        raise
