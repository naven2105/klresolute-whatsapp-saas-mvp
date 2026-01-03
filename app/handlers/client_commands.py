"""
File: app/handlers/client_commands.py

Purpose:
Tier 1 Client & Admin Menu Handler

Rules:
- Admins get admin menu
- Clients & guests get client menu
- JOIN / STOP allowed for clients & guests
- Admin still authoritative
- Always respond
"""

import os

from app.outbound.meta import MetaWhatsAppClient
from app.outbound.settings import load_meta_settings
from app.profiles.client_profile import ABOUT_TEXT
from app.services.contacts_service import add_contact, remove_contact


# =========================
# Menus
# =========================

ADMIN_MENU_TEXT = (
    "🛠️ Admin Menu\n\n"
    "ADD CLIENT: <number>\n"
    "REMOVE CLIENT: <number>\n"
    "SEND: <number> <message>\n"
    "BROADCAST: <message>\n"
    "COUNT\n"
    "PAUSE\n\n"
    "📸 Send an image to broadcast it."
)

CLIENT_MENU_TEXT = (
    "👋 Hi! Welcome.\n\n"
    "You can reply with one of the options below:\n\n"
    "ABOUT – Store details\n"
    "FEEDBACK: your comments here – Feedback, join, or removal requests\n"
    "JOIN – Receive updates from us\n"
    "STOP – Opt out at any time\n"
    "MENU – See this menu again\n\n"
    "If your question is about stock or availability,\n"
    "a staff member will reply shortly."
)

FEEDBACK_ACK_TEXT = (
    "🙏 Thank you for your message.\n"
    "We’ve shared it with the manager."
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
    db,
    sender_number: str,
    message_text: str,
) -> bool:
    """
    Client & guest handler.
    """

    is_admin = sender_number in ADMIN_ALLOWLIST
    keyword = (message_text or "").strip()
    upper = keyword.upper()

    # ---------------- MENU ----------------
    if upper == "MENU" or not upper:
        _send_text(
            sender_number,
            ADMIN_MENU_TEXT if is_admin else CLIENT_MENU_TEXT,
        )
        return True

    # ---------------- JOIN ----------------
    if upper == "JOIN" and not is_admin:
        added = add_contact(db, msisdn=sender_number)
        _send_text(
            sender_number,
            "✅ You’ll now receive updates from us."
            if added
            else "ℹ️ You’re already receiving updates.",
        )
        return True

    # ---------------- STOP ----------------
    if upper == "STOP" and not is_admin:
        removed = remove_contact(db, msisdn=sender_number)
        _send_text(
            sender_number,
            "🛑 You’ve been opted out. You won’t receive updates."
            if removed
            else "ℹ️ You were not subscribed.",
        )
        return True

    # ---------------- ABOUT ----------------
    if upper == "ABOUT" and not is_admin:
        _send_text(sender_number, ABOUT_TEXT)
        return True

    # ---------------- FEEDBACK ----------------
    if upper.startswith("FEEDBACK") and not is_admin:
        _send_text(sender_number, FEEDBACK_ACK_TEXT)

        admin_message = (
            "📩 Client message received\n\n"
            f"From: {sender_number}\n"
            f"Message:\n{message_text}"
        )

        for admin in ADMIN_ALLOWLIST:
            _send_text(admin, admin_message)

        return True

    # ---------------- FALLBACK ----------------
    _send_text(
        sender_number,
        ADMIN_MENU_TEXT if is_admin else CLIENT_MENU_TEXT,
    )
    return True
