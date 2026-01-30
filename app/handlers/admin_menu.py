from __future__ import annotations

"""
File: app/handlers/admin_menu.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Admin menu handling only.

Scope (LOCKED):
- Show admin menu
- Fallback for unknown admin commands
- NO surveys
- NO messaging logic

Rules:
- Admin-facing only
- Any unknown admin input MUST return the admin menu
- Menu is CLIENT-SPECIFIC
"""

import logging
from sqlalchemy.orm import Session

from app.outbound.factory import get_meta_client

# -------------------------------------------------
# Logging
# -------------------------------------------------

logger = logging.getLogger("admin_menu")

# -------------------------------------------------
# Client-specific admin menus
# -------------------------------------------------

from app.menus.admin.galitos_admin_menu import GALITOS_ADMIN_MENU
from app.menus.admin.magen_admin_menu import MAGEN_ADMIN_MENU

from app.utils.admin import is_admin_message


# -------------------------------------------------
# Helpers
# -------------------------------------------------

def _render_menu(menu: dict) -> str:
    """
    Render menu dict to WhatsApp-safe text.
    """
    lines = [menu["title"], ""]
    for section in menu.get("sections", []):
        lines.append(section["title"])
        for cmd in section.get("commands", []):
            lines.append(cmd)
        lines.append("")
    return "\n".join(lines).strip()


def _get_admin_menu_for_client(client_id: int | None) -> dict | None:
    """
    Resolve admin menu by KLResolute client.
    """
    if client_id == 2:   # Galitos
        return GALITOS_ADMIN_MENU
    if client_id == 3:   # Magen
        return MAGEN_ADMIN_MENU
    return None


# -------------------------------------------------
# Entry point
# -------------------------------------------------

def handle_admin_menu(
    *,
    db: Session,
    sender_number: str,
    message_text: str,
    business_msisdn: str,
    client_id: int | None = None,
) -> bool:
    """
    Handles admin menu display and fallback.

    Returns:
        True  -> menu shown
        False -> not an admin
    """

    logger.info(
        "ADMIN_MENU_ENTER | sender=%s | raw=%r | client_id=%s",
        sender_number,
        message_text,
        client_id,
    )

    if not is_admin_message(
        db=db,
        sender=sender_number,
        business_msisdn=business_msisdn,
    ):
        logger.info(
            "ADMIN_MENU_REJECT | sender not admin | sender=%s",
            sender_number,
        )
        return False

    meta = get_meta_client()

    try:
        menu = _get_admin_menu_for_client(client_id)

        if not menu:
            logger.error(
                "ADMIN_MENU_NO_CLIENT_MENU | sender=%s | client_id=%s",
                sender_number,
                client_id,
            )
            return True  # fail closed, no menu leak

        rendered = _render_menu(menu)

        meta.send_session_message(
            to_msisdn=sender_number,
            text=rendered,
        )

        logger.info(
            "ADMIN_MENU_SENT_OK | sender=%s | client_id=%s",
            sender_number,
            client_id,
        )

    except Exception as exc:
        logger.error(
            "ADMIN_MENU_SEND_FAIL | sender=%s | error=%s",
            sender_number,
            exc,
            exc_info=True,
        )

    return True
