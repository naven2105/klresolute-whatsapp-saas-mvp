# ==================================================
# File: inbound.py
# Path: app/clients/fatginger/inbound.py
# Project: KLResolute WhatsApp SaaS MVP
#
# Purpose:
# Sprint 2 – Core Functional Layer (FatGinger Only)
#
# Enables:
# - Menu retrieval
# - Drinks retrieval
# - Deterministic keyword handling
#
# Guard Rails:
# - Explicit business check
# - Empty message protection
# - Defensive DB handling
# - Structured logging
#
# Tables Used:
# - r_fg__menu_items
# - r_fg__beverages
#
# Isolation:
# - Tenant isolated
# - No cross-client logic
# ==================================================

from __future__ import annotations

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.messaging.client_messenger import send_message

logger = logging.getLogger("fatginger.inbound")


# ==================================================
# Helpers
# ==================================================

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


# ==================================================
# Main Inbound Entry
# ==================================================

def handle_fatginger_inbound(
    db: Session,
    sender_msisdn: str,
    business_msisdn: str,
    message_text: str,
) -> bool:

    logger.info(
        "FG_INBOUND_START | sender=%s | business=%s | text=%s",
        sender_msisdn,
        business_msisdn,
        message_text,
    )

    # Guard: message must exist
    if not message_text:
        logger.warning("FG_ABORT | reason=empty_message")
        return False

    msg = message_text.strip().lower()

    # Guard: deterministic only
    if msg not in ("menu", "food", "drinks"):
        logger.info("FG_SKIP | reason=keyword_no_match | text=%s", msg)
        return False

    try:

        # ------------------------------------------
        # MENU / FOOD
        # ------------------------------------------
        if msg in ("menu", "food"):

            logger.info("FG_QUERY | table=r_fg__menu_items")

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
                logger.warning("FG_EMPTY | table=r_fg__menu_items")
                return True

            response = _format_food_menu(rows)

            send_message(
                db=db,
                to=sender_msisdn,
                business_msisdn=business_msisdn,
                text=response,
            )

            logger.info("FG_RESPONSE_SENT | type=food_menu")

            return True

        # ------------------------------------------
        # DRINKS
        # ------------------------------------------
        if msg == "drinks":

            logger.info("FG_QUERY | table=r_fg__beverages")

            result = db.execute(
                text("""
                    SELECT name, price
                    FROM r_fg__beverages
                    WHERE active = TRUE
                    ORDER BY name
                """)
            )

            rows = result.fetchall()

            if not rows:
                logger.warning("FG_EMPTY | table=r_fg__beverages")
                return True

            response = _format_drinks(rows)

            send_message(
                db=db,
                to=sender_msisdn,
                business_msisdn=business_msisdn,
                text=response,
            )

            logger.info("FG_RESPONSE_SENT | type=drinks_menu")

            return True

    except SQLAlchemyError as e:
        logger.exception("FG_DB_ERROR | error=%s", str(e))
        return True  # handled but fail-safe

    except Exception as e:
        logger.exception("FG_UNEXPECTED_ERROR | error=%s", str(e))
        return True

    return False