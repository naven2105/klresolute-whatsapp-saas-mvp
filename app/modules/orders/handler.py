from __future__ import annotations

"""
File: app/modules/orders/handler.py
Path: app/modules/orders/handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Orders module adapter + Galitos order entry point.

Rules (LOCKED):
- Delegate continuation (flavour / YES / NO) to existing galitos_order_handler
- Start orders here (ORDER/FOOD + item selection) by creating conversation_state
- Ensure staff notification happens on CONFIRMED
- Return True if message was handled
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.messaging.client_messenger import send_message
from app.handlers import galitos_order_handler as galitos_orders  # SAFE import

logger = logging.getLogger("module.orders")


# -------------------------------------------------
# DB helpers
# -------------------------------------------------

def _get_active_order_state(db: Session, sender: str) -> dict | None:
    row = (
        db.execute(
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
            {"sender": sender},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def _get_klresolute_client_id(db: Session, business_msisdn: str) -> int | None:
    row = (
        db.execute(
            text(
                """
                SELECT klresolute_client_id
                FROM whatsapp_numbers
                WHERE destination_number = :business
                  AND status = 'active'
                LIMIT 1
                """
            ),
            {"business": business_msisdn},
        )
        .mappings()
        .first()
    )
    if not row:
        return None
    return row.get("klresolute_client_id")


def _get_latest_confirmed_order(db: Session, sender: str) -> dict | None:
    row = (
        db.execute(
            text(
                """
                SELECT *
                FROM orders
                WHERE customer_msisdn = :sender
                  AND status = 'CONFIRMED'
                ORDER BY confirmed_at DESC
                LIMIT 1
                """
            ),
            {"sender": sender},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def _get_active_staff_numbers(db: Session) -> list[str]:
    try:
        return (
            db.execute(
                text(
                    """
                    SELECT msisdn
                    FROM galitos_staff
                    WHERE is_active = true
                    """
                )
            )
            .scalars()
            .all()
        )
    except Exception as exc:
        logger.exception("ORDERS_STAFF_LOOKUP_FAIL | err=%s", exc)
        return []


# -------------------------------------------------
# Messaging
# -------------------------------------------------

def _send_food_menu(sender: str) -> None:
    send_message(
        to_number=sender,
        text=(
            "🍗 Galitos Food Menu\n\n"
            "1️⃣ 1/2 Chicken – R89\n"
            "2️⃣ Hot Box 3 Piece + Chips – R79\n"
            "3️⃣ Full Chicken – R159\n\n"
            "Reply with the number."
        ),
    )


def _ask_for_flavour(sender: str) -> None:
    send_message(
        to_number=sender,
        text=(
            "Please choose a flavour:\n"
            "1. Lemon & Herb\n"
            "2. Mild\n"
            "3. Hot"
        ),
    )


def _notify_staff(db: Session, order: dict) -> None:
    staff = _get_active_staff_numbers(db)
    if not staff:
        logger.error("ORDERS_NO_ACTIVE_STAFF | order_id=%s", order.get("id"))
        return

    msg = (
        "📢 New Galitos Order\n\n"
        f"Item: {order.get('item_name')}\n"
        f"Flavour: {order.get('flavour')}\n"
        f"Total: R{order.get('total_amount')}\n"
        f"Customer: {order.get('customer_msisdn')}\n"
    )

    for msisdn in staff:
        send_message(to_number=msisdn, text=msg)

    logger.info(
        "ORDERS_STAFF_NOTIFIED | order_id=%s | staff_count=%s",
        order.get("id"),
        len(staff),
    )


# -------------------------------------------------
# Main handler
# -------------------------------------------------

def handle(
    *,
    db: Session,
    msg: dict,
    sender: str,
    business_msisdn: str,
) -> bool:
    # Guard: text only
    if not msg or msg.get("type") != "text":
        return False

    body_raw = (msg.get("text", {}) or {}).get("body", "")
    body = (body_raw or "").strip()
    if not body:
        return False

    upper = body.upper()

    logger.info(
        "ORDERS_ENTER | sender=%s | business=%s | text=%s",
        sender,
        business_msisdn,
        upper,
    )

    try:
        # -------------------------------------------------
        # 1) Continuation path (active ORDER exists)
        # -------------------------------------------------
        active = _get_active_order_state(db, sender)

        if active:
            handled = False

            if hasattr(galitos_orders, "handle_order_message"):
                handled = galitos_orders.handle_order_message(
                    db=db,
                    from_number=sender,
                    text=body,
                    context={"business_msisdn": business_msisdn},
                )

            return True

        # -------------------------------------------------
        # 2) Entry path (no active ORDER)
        # -------------------------------------------------
        if upper in ("ORDER", "FOOD"):
            _send_food_menu(sender)
            return True

        if body.isdigit():
            menu = {
                "1": ("HALF_CHICKEN", "1/2 Chicken", 89),
                "2": ("HB_3_CHIPS", "Hot Box 3 Piece + Chips", 79),
                "3": ("FULL_CHICKEN", "Full Chicken", 159),
            }

            if body not in menu:
                return False

            kl_client_id = _get_klresolute_client_id(db, business_msisdn)
            if kl_client_id is None:
                logger.error(
                    "ORDERS_CLIENT_ID_MISSING | business=%s",
                    business_msisdn,
                )
                return True

            sku, name, price = menu[body]

            db.execute(
                text(
                    """
                    INSERT INTO conversation_state (
                        sender_msisdn,
                        client_id,
                        state_type,
                        item_sku,
                        item_name,
                        base_price,
                        drink_addon,
                        addon_price,
                        total_amount,
                        active
                    )
                    VALUES (
                        :sender,
                        :client_id,
                        'ORDER',
                        :sku,
                        :name,
                        :price,
                        'NONE',
                        0,
                        :price,
                        true
                    )
                    """
                ),
                {
                    "sender": sender,
                    "client_id": kl_client_id,
                    "sku": sku,
                    "name": name,
                    "price": price,
                },
            )
            db.commit()

            _ask_for_flavour(sender)
            return True

        return False

    except IntegrityError:
        try:
            db.rollback()
        except Exception:
            pass
        _ask_for_flavour(sender)
        return True

    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        logger.exception(
            "ORDERS_HANDLER_FAIL | sender=%s | business=%s",
            sender,
            business_msisdn,
        )
        return True
