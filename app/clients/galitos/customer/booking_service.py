from __future__ import annotations

"""
File: booking_service.py
Path: app/clients/galitos/customer/booking_service.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Galitos customer booking command handling (tenant-local).

Rules:
- Customer-only logic
- Parse booking command text
- Delegate DB write + notifications to existing booking handler
- Send customer-facing validation errors (format guidance)
"""

import re
from datetime import datetime, date
from sqlalchemy.orm import Session

from app.messaging.client_messenger import send_message
from app.clients.galitos.handlers.booking_handler import handle_booking


BOOKING_REGEX = re.compile(
    r"^book\s+(\d+)\s+(\d{1,2}/\d{1,2})\s+(\d{1,2}:\d{2})$",
    re.IGNORECASE,
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


def handle_booking_command(
    *,
    db: Session,
    sender_msisdn: str,
    business_msisdn: str,
    message_text: str,
) -> bool:
    """
    Returns True if this was a booking command (handled), otherwise False.
    """
    msg = (message_text or "").strip()
    if not msg.lower().startswith("book"):
        return False

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