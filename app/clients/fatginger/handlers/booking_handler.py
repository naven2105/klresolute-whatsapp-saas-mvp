# ==================================================
# File: booking_handler.py
# Path: app/clients/fatginger/handlers/booking_handler.py
# Project: KLResolute WhatsApp SaaS MVP
#
# Sprint 16 – FatGinger Campaign & Alert Standardisation
#
# Purpose:
# Dedicated FatGinger booking handler
#
# Isolation:
# - No dispatcher changes
# - No cross-tenant impact
# - Staff alerts standardised
# ==================================================

from __future__ import annotations

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.messaging.client_messenger import send_message

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
    # 2. Customer confirmation
    # --------------------------------------------------
    send_message(
        db=db,
        business_msisdn=business_msisdn,
        to_number=sender_msisdn,
        text="Your booking request has been received. The restaurant will confirm shortly.",
    )

    # --------------------------------------------------
    # 3. Staff alert (standardised template)
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

        alert_variable = (
            f"New booking | "
            f"{requested_date.strftime('%d/%m')} "
            f"{requested_time.strftime('%H:%M')} | "
            f"{guests} guests | "
            f"{sender_msisdn}. Please confirm."
        )

        for row in staff_rows:
            send_message(
                db=db,
                business_msisdn=business_msisdn,
                to_number=row.msisdn,
                template_name="klr_notification_v2__english_us",
                template_params=[alert_variable],
            )

    except Exception:
        logger.exception("FG_STAFF_FORWARD_FAIL")