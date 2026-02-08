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

    if not row:
        logger.info(
            "ORDERS_STATE_NONE | sender=%s",
            sender,
        )
        return None

    logger.info(
        "ORDERS_STATE_ACTIVE | sender=%s | state_id=%s",
        sender,
        row.get("id"),
    )
    return dict(row)


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

    if not row or row.get("klresolute_client_id") is None:
        logger.error(
            "ORDERS_CLIENT_ID_LOOKUP_FAIL | business=%s",
            business_msisdn,
        )
        return None

    logger.info(
        "ORDERS_CLIENT_ID_RESOLVED | business=%s | client_id=%s",
        business_msisdn,
        row["klresolute_client_id"],
    )
    return row["klresolute_client_id"]


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

    if not row:
        logger.info(
            "ORDERS_LATEST_NONE | sender=%s",
            sender,
        )
        return None

    return dict(row)


def _get_active_staff_numbers(db: Session) -> list[str]:
    try:
        rows = (
            db.execute(
                text(
                    """
                    SELECT msisdn
                    FROM galitos_staff
                    WHERE is_active = true
                    ORDER BY msisdn
                    """
                )
            )
            .scalars()
            .all()
        )

        if not rows:
            logger.error(
                "ORDERS_STAFF_EMPTY | table=galitos_staff | is_active=true"
            )
            return []

        logger.info(
            "ORDERS_STAFF_RESOLVED | count=%s | staff=%s",
            len(rows),
            ",".join(rows),
        )
        return rows

    except Exception as exc:
        logger.exception(
            "ORDERS_STAFF_LOOKUP_FAIL | err=%s",
            exc,
        )
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
    logger.info(
        "ORDERS_NOTIFY_ENTER | order_id=%s",
        order.get("id"),
    )

    staff = _get_active_staff_numbers(db)
    if not staff:
        logger.error(
            "ORDERS_NOTIFY_ABORTED | reason=no_active_staff | order_id=%s",
            order.get("id"),
        )
        return

    msg = (
        "📢 New Galitos Order\n\n"
        f"Item: {order.get('item_name')}\n"
        f"Flavour: {order.get('flavour')}\n"
        f"Total: R{order.get('total_amount')}\n"
        f"Customer: {order.get('customer_msisdn')}\n"
    )

    for msisdn in staff:
        try:
            send_message(to_number=msisdn, text=msg)
            logger.info(
                "ORDERS_STAFF_SENT | order_id=%s | staff=%s",
                order.get("id"),
                msisdn,
            )
        except Exception as exc:
            logger.exception(
                "ORDERS_STAFF_SEND_FAIL | order_id=%s | staff=%s | err=%s",
                order.get("id"),
                msisdn,
                exc,
            )

    logger.info(
        "ORDERS_STAFF_NOTIFY_DONE | order_id=%s | staff_count=%s",
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
    if not msg or msg.get("type") != "text":
        logger.info(
            "ORDERS_SKIP_NON_TEXT | sender=%s",
            sender,
        )
        return False

    body_raw = (msg.get("text", {}) or {}).get("body", "")
    body = (body_raw or "").strip()
    if not body:
        logger.info(
            "ORDERS_SKIP_EMPTY_TEXT | sender=%s",
            sender,
        )
        return False

    upper = body.upper()

    logger.info(
        "ORDERS_ENTER | sender=%s | business=%s | text=%s",
        sender,
        business_msisdn,
        upper,
    )

    try:
        active = _get_active_order_state(db, sender)

        if active:
            if hasattr(galitos_orders, "handle_order_message"):
                galitos_orders.handle_order_message(
                    db=db,
                    from_number=sender,
                    text=body,
                    context={"business_msisdn": business_msisdn},
                )
            return True

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
                logger.info(
                    "ORDERS_INVALID_MENU_SELECTION | sender=%s | value=%s",
                    sender,
                    body,
                )
                return False

            kl_client_id = _get_klresolute_client_id(db, business_msisdn)
            if kl_client_id is None:
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

            logger.info(
                "ORDERS_STATE_CREATED | sender=%s | item=%s",
                sender,
                name,
            )

            _ask_for_flavour(sender)
            return True

        return False

    except IntegrityError:
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning(
            "ORDERS_INTEGRITY_RECOVERED | sender=%s",
            sender,
        )
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
