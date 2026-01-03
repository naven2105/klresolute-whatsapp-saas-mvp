"""
File: app/handlers/client_commands.py

Purpose:
Tier 1 Client & Admin Menu Handler

Admin UX polish:
- Clear grouped admin menu
- No behavioural changes
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
    "Clients\n"
    "ADD CLIENT: <number>\n"
    "REMOVE CLIENT: <number>\n"
    "COUNT\n\n"
    "Messaging\n"
    "SEND: <number> <message>\n"
    "BROADCAST: <message>\n\n"
    "System\n"
    "PAUSE – stop all outbound messages\n"
    "RESUME – resume outbound messages\n\n"
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


ADMIN_ALLOWLIST = {
    n.strip()
    for n in os.getenv("OUTBOUND_TEST_ALLOWLIST", "").split(",")
    if n.strip()
}

_meta_client = MetaWhatsAppClient(settings=load_meta_settings())


def _send_text(to_number: str, text: str) -> None:
    _meta_client.send_session_message(
        to_msisdn=to_number,
        text=text,
    )


def handle_client_command(
    *,
    db,
    sender_number: str,
    message_text: str,
) -> bool:

    is_admin = sender_number in ADMIN_ALLOWLIST
    text = (message_text or "").strip()
    upper = text.upper()

    if upper == "MENU" or not upper:
        _send_text(sender_number, ADMIN_MENU_TEXT if is_admin else CLIENT_MENU_TEXT)
        return True

    if upper == "JOIN" and not is_admin:
        added = add_contact(db, msisdn=sender_number)
        _send_text(
            sender_number,
            "You’ll now receive updates from us."
            if added
            else "You’re already receiving updates.",
        )
        return True

    if upper == "STOP" and not is_admin:
        removed = remove_contact(db, msisdn=sender_number)
        _send_text(
            sender_number,
            "You’ve been opted out."
            if removed
            else "You were not subscribed.",
        )
        return True

    if upper == "ABOUT" and not is_admin:
        _send_text(sender_number, ABOUT_TEXT)
        return True

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

    _send_text(sender_number, ADMIN_MENU_TEXT if is_admin else CLIENT_MENU_TEXT)
    return True
    