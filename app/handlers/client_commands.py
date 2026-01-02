"""
client_commands.py

Tier 1 Client Interaction Handler
---------------------------------
- Keyword-based client menu
- ABOUT / FEEDBACK
- Safe fallback
"""

import os
from typing import Any, Dict

from app.outbound.meta import MetaWhatsAppClient
from app.outbound.settings import load_meta_settings

#specific client profile details
#  
from app.profiles.client_profile import ABOUT_TEXT


# =========================
# Static Text Configuration
# =========================

MENU_TEXT = (
    "👋 Hi! Welcome.\n"
    "Please reply with *one word* from the options below:\n\n"
    "ABOUT – Store details\n"
    "FEEDBACK – Send feedback to the owner\n"
    "MENU – See this menu again\n\n"
    "If your question is about stock or availability, "
    "a staff member will reply shortly."
)



FEEDBACK_ACK_TEXT = (
    "🙏 Thank you for your feedback.\n"
    "We’ve shared it with the owner."
)


# =========================
# Environment / Admin Setup
# =========================

def _get_admin_msisdn() -> str:
    admin = os.getenv("OUTBOUND_TEST_ALLOWLIST", "").strip()
    if not admin:
        raise RuntimeError("OUTBOUND_TEST_ALLOWLIST is not set")
    return admin


ADMIN_MSISDN = _get_admin_msisdn()


# =========================
# Meta Client
# =========================

_meta_client = MetaWhatsAppClient(settings=load_meta_settings())


# =========================
# Helpers
# =========================

def _normalise_text(text: str) -> str:
    return text.strip().upper()


def _send_text(to_number: str, text: str) -> None:
    _meta_client.send_session_message(to_msisdn=to_number, text=text)


def _send_menu(to_number: str) -> None:
    _send_text(to_number, MENU_TEXT)


# =========================
# Core Logic (pure)
# =========================

def _handle(client_number: str, message_text: str) -> None:
    if not message_text:
        _send_menu(client_number)
        return

    keyword = _normalise_text(message_text)

    if keyword == "MENU":
        _send_menu(client_number)
        return

    if keyword == "ABOUT":
        _send_text(client_number, ABOUT_TEXT)
        return

    if keyword == "FEEDBACK":
        _send_text(client_number, FEEDBACK_ACK_TEXT)

        admin_message = (
            "📩 Client feedback received.\n\n"
            f"From: {client_number}\n"
            "Please check WhatsApp."
        )
        _send_text(ADMIN_MSISDN, admin_message)
        return

    _send_menu(client_number)


# =========================
# Webhook Entry (REALITY)
# =========================

def handle_client_command(*args: Any, **kwargs: Any) -> None:
    """
    Expected to receive a webhook payload dict as first arg.
    """

    if not args:
        raise TypeError("handle_client_command: payload missing")

    payload: Dict[str, Any] = args[0]

    # Adjust keys ONLY if your webhook structure differs
    client_number = payload.get("from")
    message_text = payload.get("text", "")

    if not client_number:
        raise TypeError("handle_client_command: 'from' missing in payload")

    _handle(client_number, message_text)
