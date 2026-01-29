from __future__ import annotations

"""
File: app/modules/customer_menu/handler.py
Path: app/modules/customer_menu/handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Customer menu fallback module.

Responsibilities (LOCKED):
- Handle unknown / greeting messages from customers
- Send client-specific customer menu
- MUST be last module in enabled_modules
- ALWAYS return True when invoked

Rules:
- Admins are ignored
- No business logic
- No DB writes except reading profile
"""

import logging
from sqlalchemy.orm import Session

from app.profiles.client_profile import get_client_profile
from app.messaging.client_messenger import send_message

logger = logging.getLogger("module.customer_menu")


# -------------------------------------------------
# Galitos customer menu (LOCKED)
# -------------------------------------------------

GALITOS_CUSTOMER_MENU = (
    "🍗 *Welcome to Galitos!*\n\n"
    "You can:\n"
    "📋 View our menu\n"
    "🛒 Place an order\n"
    "🔥 View specials\n"
    "⏰ See trading hours\n\n"
    "Just type what you’d like, for example:\n"
    "MENU\n"
    "SPECIALS\n"
    "ORDER"
)


def handle(
    *,
    db: Session,
    msg: dict,
    sender: str,
    business_msisdn: str,
) -> bool:
    """
    Final fallback handler.
    """

    profile = get_client_profile(business_msisdn)
    if not profile:
        return False

    # Ignore admins completely
    if sender in profile.admin_numbers:
        return False

    # Only text messages trigger menu
    if msg.get("type") != "text":
        return True  # swallow silently

    body = msg.get("text", {}).get("body", "").strip().lower()

    # Any greeting or unknown text
    if profile.client_code == "GALITOS":
        logger.info(
            "CUSTOMER_MENU_SENT | client=GALITOS | sender=%s",
            sender,
        )
        send_message(
            to_number=sender,
            text=GALITOS_CUSTOMER_MENU,
        )
        return True

    return True
