from __future__ import annotations

"""
File: app/clients/pilateshq/customer_commands.py

Purpose:
PilatesHQ inbound WhatsApp handler.

Behaviour (LOCKED):
- Any inbound text → fixed autoresponse
- No menus
- No delegation
"""

import logging
from app.messaging.client_messenger import send_message

logger = logging.getLogger("clients.pilateshq")

PILATESHQ_BUSINESS_MSISDN = "27620469153"


def handle_pilateshq_customer(
    *,
    business_msisdn: str | None,
    sender: str,
) -> bool:
    """
    Returns True if handled, False otherwise.
    """

    if business_msisdn != PILATESHQ_BUSINESS_MSISDN:
        return False

    send_message(
        to_number=sender,
        text=(
            "Hi 👋 Thanks for your message.\n\n"
            "This number is used for PilatesHQ class reminders only.\n"
            "For bookings or questions, please WhatsApp Nadine on "
            "0843131635 💜"
        ),
    )

    logger.info("PILATESHQ_AUTORESPONSE_SENT | sender=%s", sender)
    return True
