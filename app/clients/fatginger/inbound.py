# ==================================================
# File: inbound.py
# Path: app/clients/fatginger/inbound.py
# Project: KLResolute WhatsApp SaaS MVP
#
# Purpose:
# FatGinger Client-Specific Menu Handler
#
# Pattern:
# - Client-specific inbound (Galitos style)
# - No module flags
# - No shared logic
# - Single transport boundary respected
# ==================================================

from __future__ import annotations

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.messaging.client_messenger import send_message

logger = logging.getLogger("fatginger.inbound")


# --------------------------------------------------
# Helpers
# --------------------------------------------------

def _format_food_menu(rows) -> str:
    burgers = []
    pizzas = []

    for row in rows:
        if row.category == "BURGER":
            burgers.append(f"• {row.name} – R{int(row.price)}")
        elif row.category == "PIZZA":
            pizzas.append(f"• {row.name} – R{int(row.price)}")

    response = "🍔 Fat Ginger Menu\n\n"

    if burgers:
        response += "BURGERS\n"
        response += "\n".join(burgers)
        response += "\n\n"

    if pizzas:
        response += "PIZZAS\n"
        response += "\n".join(pizzas)

    return response.strip()


def _format_drinks(rows) -> str:
    lines = [f"• {row.name} – R{int(row.price)}" for row in rows]

    response = "🥤 Drinks\n\n"
    response += "\n".join(lines)

    return response.strip()


# --------------------------------------------------
# Main Handler
# --------------------------------------------------

def handle_fatginger_inbound(
    db: Session,
    sender_msisdn: str,
    business_msisdn: str,
    message_text: str,
) -> bool:

    if not message_text:
        return False

    msg = message_text.strip().lower()

    try:

        # ----------------------------
        # MENU / FOOD
        # ----------------------------
        if msg in ("menu", "food"):

            result = db.execute(
                text("""
                    SELECT name, price, category
                    FROM r_fg__menu_items
                    WHERE active = TRUE
                    ORDER BY category, name
                """)
            )

            rows = result.fetchall()

            if not rows:
                return True

            response = _format_food_menu(rows)

            send_message(
                db=db,
                business_msisdn=business_msisdn,
                to_number=sender_msisdn,
                text=response,
            )

            return True

        # ----------------------------
        # DRINKS
        # ----------------------------
        if msg == "drinks":

            result = db.execute(
                text("""
                    SELECT name, price, category
                    FROM r_fg__beverages
                    WHERE active = TRUE
                    ORDER BY name
                """)
            )

            rows = result.fetchall()

            if not rows:
                return True

            response = _format_drinks(rows)

            send_message(
                db=db,
                business_msisdn=business_msisdn,
                to_number=sender_msisdn,
                text=response,
            )

            return True

    except SQLAlchemyError:
        logger.exception("FG_DB_ERROR")
        return True

    except Exception:
        logger.exception("FG_UNEXPECTED_ERROR")
        return True

    return False