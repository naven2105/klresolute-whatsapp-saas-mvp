# ==================================================
# File: menu_service.py
# Path: app/clients/rusticbarrel/customer/menu_service.py
# Project: KLResolute WhatsApp SaaS MVP
#
# Purpose:
# Rusticbarrel category-based customer menu using number selection.
# ==================================================

from __future__ import annotations

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.messaging.client_messenger import send_message

logger = logging.getLogger("rusticbarrel.menu_service")


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
                    FROM r_rusticbarrel__menu_categories
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
            "🍗 Rustic Barrel Menu\n",
            "Reply with a number:\n",
        ]

        for idx, r in enumerate(rows, start=1):
            lines.append(f"{idx}. {r['name']}")

        lines.append("\nReply MENU for main menu.")

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
                    FROM r_rusticbarrel__menu_categories
                    ORDER BY display_order
                    """
                )
            )
            .mappings()
            .all()
        )

        if index < 1 or index > len(rows):
            return True

        category = rows[index - 1]

        items = (
            db.execute(
                text(
                    """
                    SELECT name,price
                    FROM r_rusticbarrel__menu_items
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
            return True

        lines = [f"🍗 {category['name']}\n"]

        for i in items:
            lines.append(f"{i['name']} — R{i['price']}")

        lines.append("\nReply FOOD to choose another category.")
        lines.append("Reply MENU for main menu.")

        send_message(
            db=db,
            business_msisdn=business_msisdn,
            to_number=sender_msisdn,
            text="\n".join(lines),
        )

        return True

    return False