"""
File: app/handlers/client_commands.py

Purpose:
Tier 1 Client Interaction Handler

Rules:
- Always respond to any text message
- Exact keyword matching only
- No DB writes
- No shared state
"""

import os

from app.outbound.meta import MetaWhatsAppClient
from app.outbound.settings import load_meta_settings
from app.profiles.client_profile import ABOUT_TEXT


# =========================
# Static Text
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
# Admin Allowlist
# =========================

ADMIN_ALLOWLIST = {
    n.strip()
    for n in os.getenv("OUTBOUND_TEST_ALLOWLIST", "").split(",")
    if n.strip()
}


# =========================
# Meta Client
# =========================

_meta_client = MetaWhatsAppClient(settings=load_meta_settings())


def _send_text(to_number: str, text: str) -> None:
    _meta_client.send_session_message(
        to_msisdn=to_number,
        text=text,
    )


# =========================
# ENTRY POINT
# =========================

def handle_client_command(
    *,
    db,                     # required by router, NOT used
    sender_number: str,
    message_text: str,
) -> bool:
    """
    Always returns True after responding.
    """

    # Normalise
    keyword = (message_text or "").strip().upper()

    # MENU
    if keyword == "MENU" or not keyword:
        _send_text(sender_number, MENU_TEXT)
        return True

    # ABOUT
    if keyword == "ABOUT":
        _send_text(sender_number, ABOUT_TEXT)
        return True

    # FEEDBACK
    if keyword == "FEEDBACK":
        _send_text(sender_number, FEEDBACK_ACK_TEXT)

        admin_message = (
            "📩 Client feedback received.\n\n"
            f"From: {sender_number}\n"
            "Please check WhatsApp."
        )

        for admin in ADMIN_ALLOWLIST:
            _send_text(admin, admin_message)

        return True

    # FALLBACK — always show menu
    _send_text(sender_number, MENU_TEXT)
    return True
