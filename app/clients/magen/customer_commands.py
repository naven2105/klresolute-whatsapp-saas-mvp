from __future__ import annotations

"""
File: app/clients/magen/customer_commands.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Inbound handler for Magen Security WhatsApp number.

Behaviour (LOCKED):
- Route by business MSISDN (handled by dispatcher)
- Branch by staff vs public sender
- No menus
- No delegation
"""

import logging
from sqlalchemy.orm import Session

from app.messaging.client_messenger import send_message
from app.models import MagenStaff  # maps to magen_staff table

logger = logging.getLogger("clients.magen")

# Canonical Magen business number (E.164, no spaces)
MAGEN_BUSINESS_MSISDN = "27631016099"


# -------------------------------------------------
# Message Templates (LOCKED)
# -------------------------------------------------

MAGEN_PUBLIC_TEXT = (
    "Magen Security WhatsApp\n"
    "This number is reserved for internal security inspections only.\n"
    "Public chat is not supported.\n\n"
    "Please visit www.KLResolute.co.za for information."
)

MAGEN_STAFF_TEXT = (
    "Magen Security Inspection Bot\n\n"
    "Hi. Please start the inspection by sending a photo with a short caption.\n"
    "Include site status or address in the caption if possible.\n\n"
    "You may send multiple photos, notes, or location pins.\n\n"
    "Send 'done' to finish.\n\n"
    "Inspection will auto-close 5 minutes after the last input."
)


# -------------------------------------------------
# Handler
# -------------------------------------------------

def handle_magen_customer(
    *,
    db: Session,
    business_msisdn: str | None,
    sender: str,
) -> bool:
    """
    Returns True if handled, False otherwise.
    """

    if business_msisdn != MAGEN_BUSINESS_MSISDN:
        return False

    # ----------------------------------
    # Check if sender is active Magen staff
    # ----------------------------------
    staff = (
        db.query(MagenStaff)
        .filter(MagenStaff.msisdn == sender)
        .filter(MagenStaff.is_active.is_(True))
        .one_or_none()
    )

    if staff:
        send_message(
            to_number=sender,
            text=MAGEN_STAFF_TEXT,
        )
        logger.info("MAGEN_STAFF_GUIDE_SENT | sender=%s", sender)
        return True

    # ----------------------------------
    # Public / unknown sender
    # ----------------------------------
    send_message(
        to_number=sender,
        text=MAGEN_PUBLIC_TEXT,
    )
    logger.info("MAGEN_PUBLIC_BLOCK_SENT | sender=%s", sender)
    return True
