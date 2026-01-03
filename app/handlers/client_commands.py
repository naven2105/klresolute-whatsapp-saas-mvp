"""
File: app/handlers/client_commands.py

Purpose:
Tier 1 Client & Admin Menu Handler

Rules:
- Admins get admin menu
- Clients & guests get client menu
- Always respond
- No DB writes
- No shared state
"""

import os

from app.outbound.meta import MetaWhatsAppClient
from app.outbound.settings import load_meta_settings
from app.profiles.client_profile import ABOUT_TEXT


# =========================
# Menus
# =========================

ADMIN_MENU_TEXT = (
    "🛠️ *Admin Menu*\n\n"
    "ADD CLIENT: <number>\n"
    "REMOVE CLIENT: <number>\n"
    "SEND: <number> <message>\n"
    "BROADCAST: <message>\n"
    "COUNT\n"
    "PAUSE\n"
    "RESUME\n\n"
    "📸 Send an image to broadcast it."
)

CLIENT_MENU_TEXT = (
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
    Always responds.
    Admins get admin menu.
    Clients & guests get client menu.
    """

    is_admin = sender_number in ADMIN_ALLOWLIST
    keyword = (message_text or "").strip().upper()

    # MENU (admin or client)
    if keyword == "MENU" or not keyword:
        if is_admin:
            _send_text(sender_number, ADMIN_MENU_TEXT)
        else:
            _send_text(sender_number, CLIENT_MENU_TEXT)
        return True

    # ABOUT (clients & guests only)
    if keyword == "ABOUT" and not is_admin:
        _send_text(sender_number, ABOUT_TEXT)
        return True

    # FEEDBACK (clients & guests only)
    if keyword == "FEEDBACK" and not is_admin:
        _send_text(sender_number, FEEDBACK_ACK_TEXT)

        admin_message = (
            "📩 Client feedback received.\n\n"
            f"From: {sender_number}\n"
            "Please check WhatsApp."
        )

        for admin in ADMIN_ALLOWLIST:
            _send_text(admin, admin_message)

        return True

    # FALLBACK
    if is_admin:
        _send_text(sender_number, ADMIN_MENU_TEXT)
    else:
        _send_text(sender_number, CLIENT_MENU_TEXT)

    return True
