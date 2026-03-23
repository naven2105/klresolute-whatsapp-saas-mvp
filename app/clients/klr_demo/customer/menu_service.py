# ==================================================
# File: menu_service.py
# Path: app/clients/klr_demo/customer/menu_service.py
# Project: KLResolute WhatsApp SaaS MVP
#
# Patch:
# - menu command now sends PDF
# - removed unused DB/menu functions
# ==================================================

from __future__ import annotations

import random
import logging
from sqlalchemy.orm import Session

from app.messaging.client_messenger import send_message

logger = logging.getLogger("klr_demo.menu_service")


# --------------------------------------------------
# INTRO VARIATIONS
# --------------------------------------------------

INTRO_VARIATIONS = [
    "Great choice 👌",
    "That’s a solid option 👍",
    "You’ve made a good selection",
    "Let me show you some options 👇",
    "Here’s something you might like 👀",
    "Good choice — take a look 👇",
    "Here are a few options for you",
    "Let’s explore some options 👇",
    "Here are some great choices 👇",
    "Take a look at these options 👇",
]

SUGGESTION_INTROS = [
    "Here are some great options for you 👇",
    "Let me suggest something you might like 👌",
    "Here are a few recommendations 👇",
    "Take a look at these options 👀",
    "Here are some popular choices 👇",
]

# --------------------------------------------------
# BRAND + CLOSING VARIATIONS
# --------------------------------------------------

BRAND_VARIATIONS = [
    "Quality you can trust",
    "Designed with care",
    "Built for your needs",
    "Focused on great service",
]

CLOSING_VARIATIONS = [
    "Let me know what you need",
    "Happy to assist further",
    "Tell me what you're looking for",
    "Explore more options anytime",
    "Type options to see more",
]


# --------------------------------------------------
# HANDLE MENU COMMAND
# --------------------------------------------------

def handle_menu_command(
    *,
    db: Session,
    sender_msisdn: str,
    business_msisdn: str,
    message_text: str,
) -> bool:

    msg = message_text.lower().strip()

    # OPTIONS (chatbot menu)
    if msg == "options":

        send_message(
            db=db,
            business_msisdn=business_msisdn,
            to_number=sender_msisdn,
            text=(
                "How can we help?\n\n"
                "• menu — View offerings\n"
                "• specials — Latest updates\n"
                "• book — Make a booking\n"
                "• about — Learn more"
            ),
        )

        return True

    # MENU → PDF
    if msg == "menu":

        send_message(
            db=db,
            business_msisdn=business_msisdn,
            to_number=sender_msisdn,
            text=(
                "📄 Here’s our menu:\n"
                "https://klresolute.co.za/KLR_Demo_Fun.pdf"
            ),
        )

        return True

    # GENERIC HELP
    if any(word in msg for word in ["help", "recommend", "suggest"]):

        send_message(
            db=db,
            business_msisdn=business_msisdn,
            to_number=sender_msisdn,
            text=(
                "I can help you explore our offerings 👇\n\n"
                "Type menu to view our full offerings\n"
                "Or type options to see available actions"
            ),
        )

        return True


    return False
