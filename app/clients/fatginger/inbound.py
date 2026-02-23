# ==================================================
# File: inbound.py
# Path: app/clients/fatginger/inbound.py
# Project: KLResolute WhatsApp SaaS MVP
#
# Sprint 4 – Auto Join + Welcome Menu Foundation
#
# Purpose:
# FatGinger Client-Specific Inbound Handler
#
# Pattern:
# - Client-specific inbound
# - No dispatcher changes
# - Isolation preserved
# - Deterministic marketing foundation
# ==================================================

from __future__ import annotations

import logging
import re
from datetime import datetime, date
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.messaging.client_messenger import send_message

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
        # STOP / UNSUBSCRIBE
        # --------------------------------------------------
        if msg.lower() in ("stop", "unsubscribe"):

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
        # AUTO CUSTOMER CREATION (ATOMIC)
        # --------------------------------------------------
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

        # If inserted now → send welcome
        if result.rowcount == 1:

            send_message(
                db=db,
                business_msisdn=business_msisdn,
                to_number=sender_msisdn,
                text=WELCOME_MESSAGE,
            )

        # --------------------------------------------------
        # BOOKING INTAKE
        # --------------------------------------------------
        if msg.lower().startswith("book"):

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

            db.execute(
                text(
                    """
                    INSERT INTO r_fg__booking_requests
                    (customer_phone, guest_count, requested_date, requested_time)
                    VALUES (:phone, :guests, :date, :time)
                    """
                ),
                {
                    "phone": sender_msisdn,
                    "guests": guests,
                    "date": requested_date,
                    "time": requested_time,
                },
            )

            db.commit()

            send_message(
                db=db,
                business_msisdn=business_msisdn,
                to_number=sender_msisdn,
                text="Your booking request has been received. The restaurant will confirm shortly.",
            )

            try:
                result = db.execute(
                    text(
                        """
                        SELECT msisdn
                        FROM r_fg__staff
                        """
                    )
                )

                staff_rows = result.fetchall()

                for row in staff_rows:
                    send_message(
                        db=db,
                        business_msisdn=business_msisdn,
                        to_number=row.msisdn,
                        text=(
                            "New Booking Request – FatGinger\n"
                            f"Date: {requested_date.strftime('%d/%m')}\n"
                            f"Time: {requested_time.strftime('%H:%M')}\n"
                            f"Guests: {guests}\n"
                            f"From: {sender_msisdn}"
                        ),
                    )

            except Exception:
                logger.exception("FG_STAFF_FORWARD_FAIL")

            return True

        # --------------------------------------------------
        # MENU / FOOD
        # --------------------------------------------------
        if msg.lower() in ("menu", "food"):

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
        # DRINKS
        # --------------------------------------------------
        if msg.lower() == "drinks":

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