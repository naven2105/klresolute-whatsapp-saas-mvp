from __future__ import annotations

"""
File: app/handlers/tier1_router.py
Path: app/handlers/tier1_router.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Tier-1 Router (Admin + Customer entry point)

GUARD RAILS (LOCKED):
- MUST NOT handle order confirmation (YES / NO)
- MUST NOT resolve UUIDs
- MUST use INTEGER client_id only
- MUST always return admin menu for admin fallback
"""

import logging
from sqlalchemy.orm import Session

from app.outbound.factory import get_meta_client
from app.utils.admin import is_admin_message
from app.admin.menu_builder import get_admin_menu_text
from app.modules.status.reader import get_active_status
from app.clients.galitos.customer_commands import (
    handle_client_command as handle_customer_commands,
)

logger = logging.getLogger("handlers.tier1_router")


# -------------------------------------------------
# Helpers
# -------------------------------------------------

def _send_text(*, business_msisdn: str, to_number: str, text: str) -> None:
    meta = get_meta_client(business_msisdn=business_msisdn)
    meta.send_session_message(to_msisdn=to_number, text=text)


def _parse_client_id_int(raw: str | None) -> int | None:
    if not raw:
        return None
    try:
        return int(str(raw))
    except Exception:
        logger.error("CLIENT_ID_PARSE_FAIL | raw=%r", raw)
        return None


# -------------------------------------------------
# Main entry
# -------------------------------------------------

def handle_client_command(
    *,
    db: Session,
    sender_number: str,
    message_text: str,
    msg: dict | None,
    resolved_client_id: str | None,
    resolved_business_number: str | None,
) -> bool:
    business = resolved_business_number
    upper = (message_text or "").strip().upper()

    # ----------------------------------
    # HARD GUARD — NEVER TOUCH CONFIRMATION
    # ----------------------------------
    if upper in ("YES", "NO"):
        return False

    if not business:
        logger.error("TIER1_BLOCKED | missing_business_number")
        return True

    client_id_int = _parse_client_id_int(resolved_client_id)
    if client_id_int is None:
        logger.error(
            "TIER1_BLOCKED | invalid_client_id | sender=%s | business=%s",
            sender_number,
            business,
        )
        return True

    # ----------------------------------
    # ADMIN PATH
    # ----------------------------------
    is_admin = is_admin_message(
        db=db,
        sender=sender_number,
        business_msisdn=business,
    )

    if is_admin:
        logger.info(
            "ADMIN_MESSAGE | sender=%s | business=%s | text=%r",
            sender_number,
            business,
            message_text,
        )

        # Always show full admin menu (explicit or fallback)
        if upper == "MENU" or True:
            menu_text = get_admin_menu_text(
                db=db,
                client_id=client_id_int,
            )
            _send_text(
                business_msisdn=business,
                to_number=sender_number,
                text=menu_text,
            )
            return True

    # ----------------------------------
    # CUSTOMER PATH
    # ----------------------------------
    logger.info(
        "CUSTOMER_MESSAGE | sender=%s | business=%s | text=%r",
        sender_number,
        business,
        message_text,
    )

    # Status banner (if active)
    status_text = get_active_status(
        db=db,
        business_msisdn=business,
    )
    if status_text:
        _send_text(
            business_msisdn=business,
            to_number=sender_number,
            text=f"⚠️ NOTICE\n\n{status_text}\n\n———",
        )

    return bool(
        handle_customer_commands(
            db=db,
            sender=sender_number,
            msg=msg or {"type": "text", "text": {"body": message_text}},
            client_id=str(client_id_int),
            business_msisdn=business,
        )
    )
