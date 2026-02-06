from __future__ import annotations

"""
File: app/handlers/tier1_router.py
Path: app/handlers/tier1_router.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Tier-1 Router (final, thin coordinator)

Responsibilities:
- Order guard (YES / NO)
- Admin detection
- Admin command routing
- Mandatory admin fallback
- Customer routing

LOCKED:
- No business logic
- No menu building
- No DB schema assumptions
"""

import logging
from sqlalchemy.orm import Session

from app.utils.admin import is_admin_message
from app.handlers.admin_menu_builder import build_admin_menu
from app.handlers.admin_fallback import handle_admin_fallback
from app.handlers.tier1_customer_entry import handle_customer_entry
from app.outbound.factory import get_meta_client

logger = logging.getLogger("handlers.tier1_router")


def handle_client_command(
    *,
    db: Session,
    sender_number: str,
    message_text: str,
    msg: dict | None = None,
    resolved_client_id: str | None = None,
    resolved_business_number: str | None = None,
    resolved_phone_number_id: str | None = None,
) -> bool:
    """
    Single Tier-1 entry point.
    """

    try:
        business = resolved_business_number
        upper = (message_text or "").strip().upper()

        # --------------------------------------------------
        # HARD ORDER GUARD
        # --------------------------------------------------
        if upper in ("YES", "NO"):
            logger.info(
                "TIER1_BYPASS_ORDER_CONFIRMATION | sender=%s",
                sender_number,
            )
            return False

        # --------------------------------------------------
        # ADMIN PATH
        # --------------------------------------------------
        if business and is_admin_message(
            db=db,
            sender=sender_number,
            business_msisdn=business,
        ):
            logger.info(
                "TIER1_ADMIN_MESSAGE | sender=%s | text=%r",
                sender_number,
                message_text,
            )

            # Explicit MENU command
            if upper == "MENU":
                menu_text = build_admin_menu(
                    db=db,
                    business_msisdn=business,
                )
                meta = get_meta_client(business_msisdn=business)
                meta.send_session_message(
                    to_msisdn=sender_number,
                    text=menu_text,
                )
                return True

            # Anything else → mandatory fallback
            handle_admin_fallback(
                db=db,
                sender_number=sender_number,
                business_msisdn=business,
            )
            return True

        # --------------------------------------------------
        # CUSTOMER PATH
        # --------------------------------------------------
        return handle_customer_entry(
            db=db,
            sender_number=sender_number,
            message_text=message_text,
            msg=msg,
            resolved_client_id=resolved_client_id,
            resolved_business_number=business,
        )

    except Exception:
        logger.exception(
            "TIER1_ROUTER_FATAL | sender=%s",
            sender_number,
        )
        return True
