from __future__ import annotations

"""
File: menu_service.py
Path: app/clients/galitos/customer/menu_service.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Galitos customer food & drinks command handling (tenant-local).

Rules:
- Customer-only logic
- No dispatcher logic
- DB-driven rendering
- Returns True if handled
"""

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.messaging.client_messenger import send_message


# --------------------------------------------------
# FOOD MENU (previously handled "menu")
# --------------------------------------------------
def handle_menu_command(
    *,
    db: Session,
    sender_msisdn: str,
    business_msisdn: str,
    message_text: str,
) -> bool:

    msg = (message_text or "").strip().lower()

    # 🔒 NOW ONLY "food"
    if msg != "food":
        return False

    rows = db.execute(
        text(
            """
            SELECT name, price, category
            FROM r_fg__menu_items
            WHERE active = TRUE
            ORDER BY category, name
            """
        )
    ).fetchall()

    if not rows:
        send_message(
            db=db,
            business_msisdn=business_msisdn,
            to_number=sender_msisdn,
            text="Food menu is currently unavailable.",
        )
        return True

    lines = ["🍔 Food Menu\n"]

    current_category = None

    for row in rows:
        if row.category != current_category:
            current_category = row.category
            lines.append(f"\n{current_category}")

        lines.append(f"- {row.name} — R{row.price}")

    send_message(
        db=db,
        business_msisdn=business_msisdn,
        to_number=sender_msisdn,
        text="\n".join(lines),
    )

    return True


# --------------------------------------------------
# DRINKS MENU
# --------------------------------------------------
def handle_drinks_command(
    *,
    db: Session,
    sender_msisdn: str,
    business_msisdn: str,
    message_text: str,
) -> bool:

    msg = (message_text or "").strip().lower()

    if msg != "drinks":
        return False

    rows = db.execute(
        text(
            """
            SELECT name, price, category
            FROM r_fg__beverages
            WHERE active = TRUE
            ORDER BY category, name
            """
        )
    ).fetchall()

    if not rows:
        send_message(
            db=db,
            business_msisdn=business_msisdn,
            to_number=sender_msisdn,
            text="Drinks menu is currently unavailable.",
        )
        return True

    lines = ["🥤 Drinks Menu\n"]

    current_category = None

    for row in rows:
        if row.category != current_category:
            current_category = row.category
            lines.append(f"\n{current_category}")

        lines.append(f"- {row.name} — R{row.price}")

    send_message(
        db=db,
        business_msisdn=business_msisdn,
        to_number=sender_msisdn,
        text="\n".join(lines),
    )

    return True