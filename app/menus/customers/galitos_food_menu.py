from __future__ import annotations

"""
File: app/menus/customers/galitos_food_menu.py
Path: app/menus/customers/galitos_food_menu.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Galitos food ordering flow.

SPRINT: UUID Identity Enforcement + DB-Driven Meta Sender

Changes:
- Removed global Meta client
- Resolve Meta client per request (business scoped)
- Added DB rollback safety
- No functionality removed

Rules:
- No environment-based sender identity
- All outbound must be business scoped
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text as sql_text

from app.outbound.factory import get_meta_client

logger = logging.getLogger("galitos.food")


# ----------------------------------
# Helpers
# ----------------------------------

def _get_active_order(db: Session, sender: str):
    return db.execute(
        sql_text(
            """
            SELECT *
            FROM conversation_state
            WHERE sender_msisdn = :sender
              AND active = TRUE
              AND state_type = 'ORDER'
            LIMIT 1
            """
        ),
        {"sender": sender},
    ).mappings().first()


def _ask_for_flavour(
    *,
    db: Session,
    business_msisdn: str,
    sender: str,
):
    meta = get_meta_client(business_msisdn=business_msisdn)

    meta.send_session_message(
        to_msisdn=sender,
        text=(
            "Please choose a flavour:\n"
            "1️⃣ Lemon & Herb\n"
            "2️⃣ Mild\n"
            "3️⃣ Hot"
        ),
    )


def _map_flavour(choice: str) -> str | None:
    return {
        "1": "L",
        "2": "M",
        "3": "H",
    }.get(choice)


# ----------------------------------
# Main handler
# ----------------------------------

def handle_galitos_menu(
    *,
    db: Session,
    sender_number: str,
    message_text: str,
    client_id: str,
    business_msisdn: str,
) -> bool:

    meta = get_meta_client(
    db=db,
    business_msisdn=business_msisdn,
    )

    user_text = message_text.strip()
    upper = user_text.upper()

    try:
        # ----------------------------------
        # ACTIVE ORDER → FLAVOUR SELECTION
        # ----------------------------------
        active = _get_active_order(db, sender_number)

        if active and active["flavour"] is None:
            if user_text.isdigit():
                flavour = _map_flavour(user_text)
                if not flavour:
                    _ask_for_flavour(
                        db=db,
                        business_msisdn=business_msisdn,
                        sender=sender_number,
                    )
                    return True

                db.execute(
                    sql_text(
                        """
                        UPDATE conversation_state
                        SET flavour = :flavour
                        WHERE id = :id
                        """
                    ),
                    {"flavour": flavour, "id": active["id"]},
                )
                db.commit()

                meta.send_session_message(
                    to_msisdn=sender_number,
                    text=(
                        f"✅ {active['item_name']}\n"
                        f"Price: R{active['total_amount']}\n\n"
                        "Reply YES to confirm\n"
                        "Reply NO to cancel"
                    ),
                )
                return True

            _ask_for_flavour(
                db=db,
                business_msisdn=business_msisdn,
                sender=sender_number,
            )
            return True

        # ----------------------------------
        # FOOD MENU
        # ----------------------------------
        if upper in ("FOOD", "ORDER"):
            meta.send_session_message(
                to_msisdn=sender_number,
                text=(
                    "🍗 Welcome to Galitos\n\n"
                    "1️⃣ 1/2 Chicken – R89\n"
                    "2️⃣ Hot Box 3 Piece + Chips – R79\n"
                    "3️⃣ Full Chicken – R159\n\n"
                    "Reply with the number."
                ),
            )
            return True

        # ----------------------------------
        # ITEM SELECTION → CREATE STATE
        # ----------------------------------
        if user_text.isdigit():
            menu = {
                "1": ("HALF_CHICKEN", "1/2 Chicken", 89),
                "2": ("HB_3_CHIPS", "Hot Box 3 Piece + Chips", 79),
                "3": ("FULL_CHICKEN", "Full Chicken", 159),
            }

            if user_text not in menu:
                return False

            sku, name, price = menu[user_text]

            db.execute(
                sql_text(
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
                        TRUE
                    )
                    """
                ),
                {
                    "sender": sender_number,
                    "client_id": client_id,
                    "sku": sku,
                    "name": name,
                    "price": price,
                },
            )
            db.commit()

            _ask_for_flavour(
                db=db,
                business_msisdn=business_msisdn,
                sender=sender_number,
            )
            return True

        return False

    except Exception:
        db.rollback()
        logger.exception(
            "GALITOS_MENU_FATAL | sender=%s",
            sender_number,
        )
        return True
