# ==================================================
# File: booking_handler.py
# Path: app/clients/fatginger/handlers/booking_handler.py
# Project: KLResolute WhatsApp SaaS MVP
#
# Update:
# - Staff template failure no longer aborts booking flow
# - Admin/customer confirmation always executes
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
    # 2. Staff alert (do NOT abort if template fails)
    # --------------------------------------------------
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

        booking_sentence = (
            f"Booking {requested_date.strftime('%d/%m')} "
            f"{requested_time.strftime('%H:%M')} "
            f"{guests} guests {sender_msisdn}"
        )

        for row in staff_rows:
            send_message(
                db=db,
                business_msisdn=business_msisdn,
                to_number=row.msisdn.replace("0", "27", 1)
                if row.msisdn.startswith("0")
                else row.msisdn,
                template_name=FG_ORDER_NOTIFICATION,
                template_params=[booking_sentence],
            )

    except Exception:
        logger.exception("FG_STAFF_TEMPLATE_FAIL_CONTINUE")

    # --------------------------------------------------
    # 3. Customer confirmation (ALWAYS execute)
    # --------------------------------------------------
    send_message(
        db=db,
        business_msisdn=business_msisdn,
        to_number=sender_msisdn,
        text="Your booking request has been received. The restaurant will confirm shortly.",
    )