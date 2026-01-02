"""
app/handlers/client_commands.py

Tier 1 Client Interaction Handler
---------------------------------
- Keyword-based client menu
- ABOUT / FEEDBACK
- Safe fallback
- Must be compatible with webhooks.py calling conventions

Rules enforced:
- Exact keyword matching only
- No shared state
- No database writes
- Deterministic behaviour
"""

import os
from typing import Any, Dict, Optional, Tuple

from app.outbound.meta import MetaWhatsAppClient
from app.outbound.settings import load_meta_settings

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


def _extract_from_payload(payload: Dict[str, Any]) -> Tuple[Optional[str], str]:
    """
    Try common payload shapes.
    We only need:
      - client_number (sender)
      - message_text
    """
    client_number = (
        payload.get("from")
        or payload.get("client_number")
        or payload.get("sender")
        or payload.get("from_msisdn")
        or payload.get("wa_id")
    )

    message_text = (
        payload.get("text")
        or payload.get("message_text")
        or payload.get("body")
        or ""
    )

    if isinstance(message_text, dict):
        # Sometimes text is nested like {"body": "..."}
        message_text = message_text.get("body", "")

    return (client_number, str(message_text))


def _extract_from_args_kwargs(args: Tuple[Any, ...], kwargs: Dict[str, Any]) -> Tuple[Optional[str], str]:
    """
    webhooks.py may call:
      handle_client_command(client_number=..., message_text=..., db=...)
    OR pass a dict payload as first positional argument.
    We support both safely.
    """

    # 1) Keyword args (most likely in your case)
    client_number = (
        kwargs.get("client_number")
        or kwargs.get("from_msisdn")
        or kwargs.get("sender_msisdn")
        or kwargs.get("sender")
        or kwargs.get("from")
    )

    message_text = (
        kwargs.get("message_text")
        or kwargs.get("text")
        or kwargs.get("body")
        or ""
    )

    # If a payload dict is provided in kwargs
    payload = kwargs.get("payload") or kwargs.get("data")
    if isinstance(payload, dict):
        cn, mt = _extract_from_payload(payload)
        client_number = client_number or cn
        message_text = message_text or mt

    # 2) Positional payload dict fallback
    if (not client_number) and args:
        first = args[0]
        if isinstance(first, dict):
            cn, mt = _extract_from_payload(first)
            client_number = client_number or cn
            message_text = message_text or mt
        elif isinstance(first, str):
            # Some routers might pass client_number first
            client_number = first
            if len(args) >= 2 and isinstance(args[1], str):
                message_text = args[1]

    # Normalise message_text
    if message_text is None:
        message_text = ""
    if isinstance(message_text, dict):
        message_text = message_text.get("body", "")

    return (client_number, str(message_text))


# =========================
# Core Logic
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

    # Fallback
    _send_menu(client_number)


# =========================
# Entry Point Expected by webhooks.py
# =========================

def handle_client_command(*args: Any, **kwargs: Any) -> bool:
    """
    Returns:
      True  -> we handled it (we sent a reply/menu/about/feedback)
      False -> we could not determine client_number; allow other routing
    Never raises.
    """

    client_number, message_text = _extract_from_args_kwargs(args, kwargs)

    if not client_number:
        # Don't crash the webhook. Let routing continue.
        return False

    _handle(client_number, message_text)
    return True
