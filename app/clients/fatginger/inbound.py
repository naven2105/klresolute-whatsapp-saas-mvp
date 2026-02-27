# ==================================================
# File: inbound.py
# Path: app/clients/fatginger/inbound.py
# Project: KLResolute WhatsApp SaaS MVP
#
# Sprint 16 – Role Separation Foundation
#
# Purpose:
# FatGinger Client-Specific Inbound Handler
#
# Update:
# - Added role detection (admin, staff, customer)
# - Prevented admin/staff from auto customer registration
# - STOP logic restricted to customers only
#
# Isolation:
# - No dispatcher changes
# - No campaign logic yet
# - Booking logic unchanged
# ==================================================

from __future__ import annotations

import logging
import re
from datetime import datetime, date
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.messaging.client_messenger import send_message
from app.clients.fatginger.handlers.booking_handler import handle_booking

logger = logging.getLogger("fatginger.inbound")


# --------------------------------------------------
# Helpers
# --------------------------------------------------

BOOKING_REGEX = re.compile(
    r"^book\s+(\d+)\s+(\d{1,2}/\d{1,2})\s+(\d{1,2}:\d{2})$",
    re.IGNORECASE,
)


WELCOME_MESSAGE = (
    "Welcome to FatGinger 🍔🔥\n"
    "You can:\n"
    "• Type menu to see food\n"
    "• Type drinks to see beverages\n"
    "• Type book to reserve a table\n"
    "Reply STOP anytime to unsubscribe."
)


STOP_CONFIRMATION = (
    "You have been unsubscribed from marketing messages.\n"
    "You can still use menu and booking anytime."
)


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


def _parse_booking(message_text: str):
    match = BOOKING_REGEX.match(message_text.strip())
    if not match:
        return None

    guests_raw, date_raw, time_raw = match.groups()

    try:
        guests = int(guests_raw)

        day, month = map(int, date_raw.split("/"))
        current_year = datetime.utcnow().year

        requested_date = date(current_year, month, day)

        if requested_date < datetime.utcnow().date():
            requested_date = date(current_year + 1, month, day)

        requested_time = datetime.strptime(time_raw, "%H:%M").time()

        return guests, requested_date, requested_time

    except Exception:
        return None


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

    msg = message_text.strip()

    try:

        # --------------------------------------------------
        # Role Detection
        # --------------------------------------------------
        role = "customer"

        admin_check = db.execute(
            text("SELECT 1 FROM r_fg__admins WHERE msisdn = :phone LIMIT 1"),
            {"phone": sender_msisdn},
        ).fetchone()

        if admin_check:
            role = "admin"
        else:
            staff_check = db.execute(
                text("SELECT 1 FROM r_fg__staff WHERE msisdn = :phone LIMIT 1"),
                {"phone": sender_msisdn},
            ).fetchone()

            if staff_check:
                role = "staff"

        # --------------------------------------------------
        # STOP / UNSUBSCRIBE (Customers Only)
        # --------------------------------------------------
        if role == "customer" and msg.lower() in ("stop", "unsubscribe"):

            db.execute(
                text(
                    """
                    UPDATE r_fg__customers
                    SET marketing_opt_in = FALSE,
                        opt_out_timestamp = NOW()
                    WHERE phone = :phone
                    """
                ),
                {"phone": sender_msisdn},
            )

            db.commit()

            send_message(
                db=db,
                business_msisdn=business_msisdn,
                to_number=sender_msisdn,
                text=STOP_CONFIRMATION,
            )

            return True

        # --------------------------------------------------
        # AUTO REGISTER CUSTOMER (Customers Only)
        # --------------------------------------------------
        if role == "customer":

            result = db.execute(
                text(
                    """
                    INSERT INTO r_fg__customers (phone)
                    VALUES (:phone)
                    ON CONFLICT (phone) DO NOTHING
                    """
                ),
                {"phone": sender_msisdn},
            )

            db.commit()

            if result.rowcount == 1:

                send_message(
                    db=db,
                    business_msisdn=business_msisdn,
                    to_number=sender_msisdn,
                    text=WELCOME_MESSAGE,
                )

        # --------------------------------------------------
        # BOOKING (Customers Only)
        # --------------------------------------------------
        if role == "customer" and msg.lower().startswith("book"):

            parsed = _parse_booking(msg)

            if not parsed:
                send_message(
                    db=db,
                    business_msisdn=business_msisdn,
                    to_number=sender_msisdn,
                    text="Please use this format:\nbook 4 22/02 19:00",
                )
                return True

            guests, requested_date, requested_time = parsed

            handle_booking(
                db=db,
                sender_msisdn=sender_msisdn,
                business_msisdn=business_msisdn,
                guests=guests,
                requested_date=requested_date,
                requested_time=requested_time,
            )

            return True

        # --------------------------------------------------
        # MENU (Customers Only)
        # --------------------------------------------------
        if role == "customer" and msg.lower() in ("menu", "food"):

            result = db.execute(
                text(
                    """
                    SELECT name, price, category
                    FROM r_fg__menu_items
                    WHERE active = TRUE
                    ORDER BY category, name
                    """
                )
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

        # --------------------------------------------------
        # DRINKS (Customers Only)
        # --------------------------------------------------
        if role == "customer" and msg.lower() == "drinks":

            result = db.execute(
                text(
                    """
                    SELECT name, price, category
                    FROM r_fg__beverages
                    WHERE active = TRUE
                    ORDER BY name
                    """
                )
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
        db.rollback()
        logger.exception("FG_DB_ERROR")
        return True

    except Exception:
        db.rollback()
        logger.exception("FG_UNEXPECTED_ERROR")
        return True

    return False