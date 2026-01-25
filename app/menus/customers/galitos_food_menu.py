from __future__ import annotations

"""
File: app/menus/customers/galitos_food_menu.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Galitos food ordering flow.

NOTE:
State is driven by conversation_state.
This file must NOT override state-based routing.
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text as sql_text

from app.outbound.factory import get_meta_client

logger = logging.getLogger("galitos.food")
meta = get_meta_client()


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
            LIMIT 1
            """
        ),
        {"sender": sender},
    ).mappings().first()


def _ask_for_flavour(sender: str):
    meta.send_session_message(
        to_msisdn=sender,
        text=(
            "Please choose a flavour:\n"
            "1️⃣ Mild\n"
            "2️⃣ Medium\n"
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
) -> bool:
    user_text = message_text.strip()

    # ----------------------------------
    # STATE-FIRST routing
    # ----------------------------------
    active = _get_active_order(db, sender_number)

    if active and active["flavour"] is None:
        if user_text.isdigit():
            flavour = _map_flavour(user_text)
            if not flavour:
                _ask_for_flavour(sender_number)
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
                    f"✅ {active['item_name']} selected.\n"
                    "Reply YES to confirm or NO to cancel."
                ),
            )
            return True

        _ask_for_flavour(sender_number)
        return True

    # ----------------------------------
    # FOOD keyword
    # ----------------------------------
    if user_text.upper() == "FOOD":
        meta.send_session_message(
            to_msisdn=sender_number,
            text=(
                "🍗 Welcome to Galitos\n\n"
                "1️⃣ 1/2 Chicken\n"
                "2️⃣ Hot Box 3 Piece + Chips\n\n"
                "Reply with the number."
            ),
        )
        return True

    return False
