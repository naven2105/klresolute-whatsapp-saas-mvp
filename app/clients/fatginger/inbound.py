# ==================================================
# File: inbound.py
# Path: app/clients/fatginger/inbound.py
# Project: KLResolute WhatsApp SaaS MVP
#
# Sprint 16 – Campaign Integration
#
# Purpose:
# FatGinger Client-Specific Inbound Handler
#
# Update:
# - Delegates admin messages to campaign_handler
# - Staff blocked
# - Customer flow unchanged
#
# Isolation:
# - No dispatcher changes
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
from app.clients.fatginger.handlers.campaign_handler import (
    handle_admin_message,
)

logger = logging.getLogger("fatginger.inbound")


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


def handle_fatginger_inbound(
    db: Session,
    sender_msisdn: str,
    business_msisdn: str,
    message_text: str | None,
    message_type: str,
    media_url: str | None,
) -> bool:

    # Allow image-only messages
    if not message_text and message_type != "image":
        return False

    msg = (message_text or "").strip()

    try:

        # --------------------------------------------------
        # ROLE DETECTION
        # --------------------------------------------------
        role = "customer"

        if db.execute(
            text("SELECT 1 FROM r_fg__admins WHERE msisdn = :phone LIMIT 1"),
            {"phone": sender_msisdn},
        ).fetchone():
            role = "admin"

        elif db.execute(
            text("SELECT 1 FROM r_fg__staff WHERE msisdn = :phone LIMIT 1"),
            {"phone": sender_msisdn},
        ).fetchone():
            role = "staff"

        # --------------------------------------------------
        # ADMIN
        # --------------------------------------------------
        if role == "admin":
            return handle_admin_message(
                db=db,
                sender_msisdn=sender_msisdn,
                business_msisdn=business_msisdn,
                message_text=message_text,
                message_type=message_type,
                media_url=media_url,
            )

        # --------------------------------------------------
        # STAFF (No interaction)
        # --------------------------------------------------
        if role == "staff":
            return True

        # --------------------------------------------------
        # CUSTOMER LOGIC
        # --------------------------------------------------

        # STOP / UNSUBSCRIBE
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

        # AUTO REGISTER
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

        # BOOKING
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

            handle_booking(
                db=db,
                sender_msisdn=sender_msisdn,
                business_msisdn=business_msisdn,
                guests=guests,
                requested_date=requested_date,
                requested_time=requested_time,
            )

            return True

        # ANNOUNCEMENT RETRIEVAL
        if msg.lower() == "announcement":
            result = db.execute(
                text(
                    """
                    SELECT type, message, image_url
                    FROM r_fg__campaigns
                    ORDER BY sent_at DESC
                    LIMIT 1
                    """
                )
            ).fetchone()

            if not result:
                send_message(
                    db=db,
                    business_msisdn=business_msisdn,
                    to_number=sender_msisdn,
                    text="No active announcements at the moment.",
                )
                return True

            if result.type == "text":
                formatted = (
                    "📢 Fat Ginger Announcement\n\n"
                    f"{result.message}"
                )

                send_message(
                    db=db,
                    business_msisdn=business_msisdn,
                    to_number=sender_msisdn,
                    text=formatted,
                )
            else:
                send_message(
                    db=db,
                    business_msisdn=business_msisdn,
                    to_number=sender_msisdn,
                    image_url=result.image_url,
                    caption=result.message,
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