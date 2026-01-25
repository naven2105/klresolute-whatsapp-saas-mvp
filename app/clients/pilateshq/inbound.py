from __future__ import annotations

"""
File: app/clients/pilateshq/inbound.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Inbound handler for PilatesHQ WhatsApp number.

RULES (LOCKED):
- PilatesHQ WhatsApp is REMINDERS-ONLY
- Any inbound client message must receive a clarification response
- No booking, no menus, no delegation
"""

import logging
from sqlalchemy.orm import Session

from app.messaging.client_messenger import send_message

logger = logging.getLogger("clients.pilateshq")

# -------------------------------------------------
# PilatesHQ business number (E.164, no spaces)
# -------------------------------------------------
PILATESHQ_BUSINESS_MSISDN = "27620469153"


# -------------------------------------------------
# Message text (LOCKED)
# -------------------------------------------------
PILATESHQ_AUTOREPLY_TEXT = (
    "Hi 👋 Thanks for your message.\n\n"
    "This number is used for PilatesHQ class reminders only.\n"
    "For bookings or questions, please WhatsApp Nadine on "
    "0843131635 💜"
)


# -------------------------------------------------
# Handler
# -------------------------------------------------

def handle_inbound(
    *,
    db: Session,
    msg: dict,
    sender: str,
    business_msisdn: str,
) -> bool:
    """
    Returns True if this handler claims the message.
    """

    if business_msisdn != PILATESHQ_BUSINESS_MSISDN:
        return False

    send_message(
        to_number=sender,
        text=PILATESHQ_AUTOREPLY_TEXT,
    )

    logger.info(
        "PILATESHQ_AUTORESPONSE_SENT | sender=%s | business=%s",
        sender,
        business_msisdn,
    )
    return True
