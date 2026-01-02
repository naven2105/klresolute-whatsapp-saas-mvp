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

from app.outbound.meta import send_text_message
from app.config import OUTBOUND_TEST_ALLOWLIST


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
# Helper Functions
# =========================

def _normalise_text(text: str) -> str:
    """Normalise inbound text for exact keyword matching."""
    return text.strip().upper()


def _send_menu(to_number: str):
    send_text_message(to_number, MENU_TEXT)


# =========================
# Main Entry Point
# =========================

def handle_client_message(client_number: str, message_text: str):
    """
    Entry point for all client messages.

    Args:
        client_number (str): WhatsApp number of client
        message_text (str): Raw inbound text
    """

    if not message_text:
        _send_menu(client_number)
        return

    keyword = _normalise_text(message_text)

    # ---- MENU ----
    if keyword == "MENU":
        _send_menu(client_number)
        return

    # ---- ABOUT ----
    if keyword == "ABOUT":
        send_text_message(client_number, ABOUT_TEXT)
        return

    # ---- FEEDBACK ----
    if keyword == "FEEDBACK":
        # Acknowledge client
        send_text_message(client_number, FEEDBACK_ACK_TEXT)

        # Forward feedback notice to admin
        admin_number = OUTBOUND_TEST_ALLOWLIST
        admin_message = (
            "📩 *Client Feedback Received*\n\n"
            f"From: {client_number}\n\n"
            "Please check WhatsApp for the full message."
        )
        send_text_message(admin_number, admin_message)
        return

    # ---- FALLBACK ----
    _send_menu(client_number)
