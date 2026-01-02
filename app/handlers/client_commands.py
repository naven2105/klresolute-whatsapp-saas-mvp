"""
client_commands.py

Tier 1 Client Interaction Handler
---------------------------------
Responsibilities:
- Handle client-originated WhatsApp messages
- Provide a simple keyword-based menu
- Route feedback to admin
- Never infer intent
- Never answer stock or availability questions

Rules enforced:
- Exact keyword matching only
- No shared state
- No database writes
- One outbound reply per inbound message
"""

import os
from typing import Any

from app.outbound.meta import MetaWhatsAppClient
from app.outbound.settings import load_meta_settings


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

ABOUT_TEXT = (
    "🏪 Store Information\n\n"
    "⏰ Trading Hours:\n"
    "Mon–Sat: 8am – 6pm\n"
    "Sun & Public Holidays: Closed\n\n"
    "📍 Address:\n"
    "123 Main Road, Your Area\n\n"
    "📞 Contact:\n"
    "081 000 0000"
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
        raise RuntimeError("OUTBOUND_TEST_ALLOWLIST is not set (admin MSISDN required)")
    return admin


ADMIN_MSISDN = _get_admin_msisdn()


# =========================
# Meta Client (canonical)
# =========================

_meta_client = MetaWhatsAppClient(settings=load_meta_settings())


# =========================
# Helper Functions
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
            "Please check WhatsApp to view the message."
        )
        _send_text(ADMIN_MSISDN, admin_message)
        return

    _send_menu(client_number)


# =========================
# Webhook Compatibility Entry
# =========================

def handle_client_command(*args: Any, **kwargs: Any) -> None:
    """
    Compatibility wrapper for webhooks.py.

    Expected (somewhere in args/kwargs):
    - client_number
    - message_text
    """

    client_number = kwargs.get("client_number")
    message_text = kwargs.get("message_text")

    # Fallback: positional extraction if used
    if client_number is None and len(args) >= 1:
        client_number = args[0]

    if message_text is None and len(args) >= 2:
        message_text = args[1]

    if not client_number:
        raise TypeError("handle_client_command: client_number not provided")

    if message_text is None:
        message_text = ""

    _handle(client_number, message_text)
