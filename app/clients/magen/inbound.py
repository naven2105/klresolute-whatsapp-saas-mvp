from __future__ import annotations

"""
File: app/clients/magen/inbound.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Inbound router for Magen Security inspections.

RULES (LOCKED):
- Inspection starts automatically on FIRST photo or GPS
- No START command
- 'done' closes inspection (handled later)
- Staff vs public handled here
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.messaging.client_messenger import send_message

logger = logging.getLogger("clients.magen")

MAGEN_BUSINESS_MSISDN = "27631016099"


def _get_active_inspection(db: Session, sender: str):
    return db.execute(
        text(
            """
            SELECT inspection_id
            FROM magen_inspections
            WHERE officer_msisdn = :msisdn
              AND status = 'ACTIVE'
            LIMIT 1
            """
        ),
        {"msisdn": sender},
    ).first()


def _start_inspection(db: Session, sender: str):
    row = db.execute(
        text(
            """
            INSERT INTO magen_inspections (officer_msisdn, status)
            VALUES (:msisdn, 'ACTIVE')
            RETURNING inspection_id
            """
        ),
        {"msisdn": sender},
    ).first()
    db.commit()
    return row.inspection_id


def handle_inbound(
    *,
    db: Session,
    msg: dict,
    sender: str,
    business_msisdn: str,
) -> bool:

    if business_msisdn != MAGEN_BUSINESS_MSISDN:
        return False

    # -------------------------------
    # Check if sender is Magen staff
    # -------------------------------
    staff = db.execute(
        text(
            """
            SELECT 1
            FROM magen_staff
            WHERE msisdn = :msisdn
              AND is_active = TRUE
            LIMIT 1
            """
        ),
        {"msisdn": sender},
    ).first()

    if not staff:
        send_message(
            to_number=sender,
            text=(
                "Magen Security WhatsApp\n"
                "This number is reserved for internal inspections only.\n\n"
                "Visit www.KLResolute.co.za for information."
            ),
        )
        logger.info("MAGEN_PUBLIC_BLOCK_SENT | sender=%s", sender)
        return True

    msg_type = msg.get("type")

    # -------------------------------
    # START inspection on PHOTO or GPS
    # -------------------------------
    if msg_type in ("image", "location"):
        active = _get_active_inspection(db, sender)

        if not active:
            inspection_id = _start_inspection(db, sender)
            logger.info(
                "MAGEN_INSPECTION_STARTED | sender=%s | inspection_id=%s",
                sender,
                inspection_id,
            )

            send_message(
                to_number=sender,
                text=(
                    "📋 Inspection started.\n\n"
                    "Send photos, notes, or location.\n"
                    "Send 'done' to finish.\n\n"
                    "Inspection auto-closes after 5 minutes of inactivity."
                ),
            )

        # Message is CLAIMED (event handling comes next phase)
        return True

    # -------------------------------
    # Guidance message (text only)
    # -------------------------------
    if msg_type == "text":
        send_message(
            to_number=sender,
            text=(
                "Magen Security Inspection Bot\n\n"
                "Please start the inspection by sending a PHOTO or LOCATION.\n"
                "Send 'done' when finished."
            ),
        )
        return True

    return True
