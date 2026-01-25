from __future__ import annotations

"""
File: app/menus/customers/galitos_food_menu.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Galitos food ordering flow.

CRITICAL FIX (2026-01-25):
- Enforce STATE-FIRST routing.
- If an active order exists and flavour is missing → digits mean FLAVOUR, not item.
- Prevent infinite flavour loop.
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.outbound.factory import get_meta_client

logger = logging.getLogger("galitos.food")

meta = get_meta_client()

# ----------------------------------
# Helpers
# ----------------------------------

def _get_active_order(db: Session, sender: str):
    return db.execute(
        text(
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
    text = message_text.strip()

    # ----------------------------------
    # 1️⃣ STATE-FIRST: active order exists
    # ----------------------------------
    active = _get_active_order(db, sender_number)

    if active and active["flavour"] is None:
        # We are awaiting flavour ONLY
        if text.isdigit():
            flavour = _map_flavour(text)
            if not flavour:
                _ask_for_flavour(sender_number)
                return True

            db.execute(
                text(
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

        # Non-digit while awaiting flavour → ignore
        _ask_for_flavour(sender_number)
        return True

    # ----------------------------------
    # 2️⃣ No active order → FOOD keyword
    # ----------------------------------
    if text.upper() == "FOOD":
        meta.send_session_message(
            to_msisdn=sender_number,
            text=(
                "🍗 Galitos Menu\n\n"
                "1️⃣ 1/2 Chicken\n"
                "2️⃣ Hot Box 3 Piece + Chips\n\n"
                "Reply with the number."
            ),
        )
        return True

    # ----------------------------------
    # 3️⃣ Item selection (only if NO active order)
    # ----------------------------------
    if not active and text.isdigit():
        # NOTE: item mapping already existed — unchanged
        return False  # let existing item logic run

    return False
