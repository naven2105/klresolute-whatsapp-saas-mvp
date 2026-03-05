# ==================================================
# File: menu_service.py
# Path: app/clients/galitos/customer/menu_service.py
# Project: KLResolute WhatsApp SaaS MVP
#
# Purpose:
# Galitos category-based customer menu using number selection.
# ==================================================

from __future__ import annotations

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.messaging.client_messenger import send_message

logger = logging.getLogger("galitos.menu_service")


def handle_menu_command(
    *,
    db: Session,
    sender_msisdn: str,
    business_msisdn: str,
    message_text: str,
) -> bool:

    msg = (message_text or "").strip().lower()

    # --------------------------------------------------
    # SHOW CATEGORY MENU
    # --------------------------------------------------
    if msg == "food":

        rows = (
            db.execute(
                text(
                    """
                    SELECT id,name,display_order
                    FROM r_galitos__menu_categories
                    ORDER BY display_order
                    """
                )
            )
            .mappings()
            .all()
        )

        if not rows:
            return False

        lines = [
            "🍗 Galitos Menu\n",
            "Reply with a number:\n",
        ]

        for idx, r in enumerate(rows, start=1):
            lines.append(f"{idx}️⃣ {r['name']}")

        send_message(
            db=db,
            business_msisdn=business_msisdn,
            to_number=sender_msisdn,
            text="\n".join(lines),
        )

        return True

    # --------------------------------------------------
    # NUMBER SELECTION
    # --------------------------------------------------
    if msg.isdigit():

        index = int(msg)

        rows = (
            db.execute(
                text(
                    """
                    SELECT id,name
                    FROM r_galitos__menu_categories
                    ORDER BY display_order
                    """
                )
            )
            .mappings()
            .all()
        )

        if not rows:
            send_message(
                db=db,
                business_msisdn=business_msisdn,
                to_number=sender_msisdn,
                text="No menu categories available. Reply FOOD to try again.",
            )
            return True

        if index < 1 or index > len(rows):
            send_message(
                db=db,
                business_msisdn=business_msisdn,
                to_number=sender_msisdn,
                text="Invalid selection. Reply FOOD to view categories.",
            )
            return True

        category = rows[index - 1]

        items = (
            db.execute(
                text(
                    """
                    SELECT name,price
                    FROM r_galitos__menu_items
                    WHERE category_id = :cid
                    ORDER BY display_order
                    """
                ),
                {"cid": category["id"]},
            )
            .mappings()
            .all()
        )

        if not items:
            send_message(
                db=db,
                business_msisdn=business_msisdn,
                to_number=sender_msisdn,
                text=f"No items found for {category['name']}. Reply FOOD to choose another category.",
            )
            return True

        lines = [f"🍗 {category['name']}\n"]

        for i in items:
            lines.append(f"{i['name']} — R{i['price']}")

        lines.append("\nReply FOOD to go back.")

        send_message(
            db=db,
            business_msisdn=business_msisdn,
            to_number=sender_msisdn,
            text="\n".join(lines),
        )

        return True

    return False