from __future__ import annotations

"""
File: app/handlers/admin_fallback.py
Path: app/handlers/admin_fallback.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Mandatory admin fallback handler.
If an admin message reaches Tier-1 without being handled,
the FULL admin menu is always returned.

Rules (LOCKED):
- No DB writes
- No routing decisions
- One responsibility only
"""

import logging
from sqlalchemy.orm import Session

from app.outbound.factory import get_meta_client
from app.handlers.admin_menu_builder import build_admin_menu

logger = logging.getLogger("handlers.admin_fallback")


def handle_admin_fallback(
    *,
    db: Session,
    sender_number: str,
    business_msisdn: str,
) -> None:
    """
    Always sends the full admin menu.
    """

    try:
        menu_text = build_admin_menu(
            db=db,
            business_msisdn=business_msisdn,
        )

        meta = get_meta_client(business_msisdn=business_msisdn)
        meta.send_session_message(
            to_msisdn=sender_number,
            text=menu_text,
        )

        logger.info(
            "ADMIN_FALLBACK_MENU_SENT | admin=%s | business=%s",
            sender_number,
            business_msisdn,
        )

    except Exception:
        logger.exception(
            "ADMIN_FALLBACK_FAIL | admin=%s | business=%s",
            sender_number,
            business_msisdn,
        )
