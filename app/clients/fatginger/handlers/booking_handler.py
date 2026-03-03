# ==================================================
# File: booking_handler.py
# Path: app/clients/fatginger/handlers/booking_handler.py
# Project: KLResolute WhatsApp SaaS MVP
#
# Sprint 16 – FatGinger Booking Handler Extraction
#
# Purpose:
# Dedicated FatGinger booking handler
#
# Update:
# - Template-first business rule enforced
# - Staff template must succeed before customer confirmation
#
# Isolation:
# - No dispatcher changes
# - No cross-tenant impact
# - Uses template registry (governance preserved)
# ==================================================

from __future__ import annotations

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.messaging.client_messenger import send_message
from app.messaging.template_registry import FG_ORDER_NOTIFICATION

logger = logging.getLogger("fatginger.booking_handler")


def handle_booking(
    db: Session,
    sender_msisdn: str,
    business_msisdn: str,
    guests: int,
    requested_date,
    requested_time,
) -> None:

    # --------------------------------------------------
    # 1. Insert booking request
    # --------------------------------------------------
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

    # --------------------------------------------------
    # 2. Staff alert (template MUST succeed first)
    # --------------------------------------------------
    result = db.execute(
        text(
            """
            SELECT msisdn
            FROM r_fg__staff
            """
        )
    )

    staff_rows = result.fetchall()

    booking_sentence = (
        f"Booking {requested_date.strftime('%d/%m')} "
        f"{requested_time.strftime('%H:%M')} "
        f"{guests} guests {sender_msisdn}"
    ).replace("\n", " ").strip()

    for row in staff_rows:
        send_message(
            db=db,
            business_msisdn=business_msisdn,
            to_number=row.msisdn,
            template_name=FG_ORDER_NOTIFICATION,
            template_params=[booking_sentence],
        )

    # --------------------------------------------------
    # 3. Customer confirmation (ONLY after template success)
    # --------------------------------------------------
    send_message(
        db=db,
        business_msisdn=business_msisdn,
        to_number=sender_msisdn,
        text="Your booking request has been received. The restaurant will confirm shortly.",
    )