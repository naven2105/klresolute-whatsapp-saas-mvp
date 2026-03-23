# ==================================================
# File: booking_handler.py
# Path: app/clients/klr_demo/handlers/booking_handler.py
# Project: KLResolute WhatsApp SaaS MVP
#
# Sprint 16 – klr_demo Booking Handler Extraction
#
# Purpose:
# Dedicated klr_demo booking handler
#
# Update:
# - Staff template failure does not abort booking flow
# - Per-recipient isolation: one bad staff number must not block others
# - Skip self-send (business number) after normalisation
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
from app.messaging.template_registry import PLATFORM_CLIENT_GENERIC

logger = logging.getLogger("klr_demo.booking_handler")


def _normalise_sa_msisdn(raw: str) -> str:
    """
    Minimal SA normaliser (tenant-local):
    - '0XXXXXXXXX' -> '27XXXXXXXXX'
    - otherwise return raw trimmed
    """
    v = (raw or "").strip()
    if v.startswith("0"):
        return "27" + v[1:]
    return v


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
            INSERT INTO r_klr_demo__booking_requests
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
    # 2. Staff alert (template) — do NOT abort on failure
    #    and do NOT allow one bad recipient to block others
    # --------------------------------------------------
    try:
        result = db.execute(
            text(
                """
                SELECT msisdn
                FROM r_klr_demo__staff
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
            try:
                to_msisdn = _normalise_sa_msisdn(getattr(row, "msisdn", "") or "")

                # Skip sending template to the business number itself
                if to_msisdn == business_msisdn:
                    logger.warning(
                        "FG_STAFF_TEMPLATE_SKIP_SELF | business=%s | staff_raw=%s | staff_norm=%s",
                        business_msisdn,
                        getattr(row, "msisdn", None),
                        to_msisdn,
                    )
                    continue

                send_message(
                    db=db,
                    business_msisdn=business_msisdn,
                    to_number=to_msisdn,
                    template_name=PLATFORM_CLIENT_GENERIC,
                    template_params=[booking_sentence],
                )

            except Exception:
                logger.exception(
                    "FG_STAFF_TEMPLATE_SEND_FAIL | business=%s | staff_raw=%s",
                    business_msisdn,
                    getattr(row, "msisdn", None),
                )

    except Exception:
        logger.exception("FG_STAFF_TEMPLATE_QUERY_FAIL_CONTINUE")

    # --------------------------------------------------
    # 3. Customer confirmation (ALWAYS execute)
    # --------------------------------------------------
    send_message(
        db=db,
        business_msisdn=business_msisdn,
        to_number=sender_msisdn,
        text="Your booking request has been received. The restaurant will confirm shortly.",
    )
