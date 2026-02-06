from __future__ import annotations

"""
File: app/handlers/tier1_router.py
Path: app/handlers/tier1_router.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Tier 1 Router (Client + Admin entry point)

GUARD RAILS (LOCKED):
- MUST NOT handle order flow
- MUST NOT intercept YES / NO
- MUST NOT require profile DB for orders

DB TRUTH (VERIFIED):
- client_contacts.client_id is INTEGER (MVP reality)
- Tier-1 must NOT attempt UUID client_id resolution.
- Tier-1 must only use the upstream resolved integer client_id.

Design:
- Thin coordinator only
- Admin logic delegated to tier1_admin_handler
- Customer logic delegated to tier1_customer_handler
"""

import logging
from sqlalchemy.orm import Session

from app.utils.admin import is_admin_message

from app.handlers.tier1_admin_handler import handle_admin_command
from app.handlers.tier1_customer_handler import handle_customer_tier1

logger = logging.getLogger("handlers.tier1_router")


# =================================================
# Main handler
# =================================================

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
    Tier-1 entry point.

    Routing rules:
    - YES / NO are never handled here
    - Admins are handled first
    - Customers require resolved integer client_id
    """

    try:
        upper = (message_text or "").strip().upper()
        business_number = resolved_business_number

        logger.info(
            "TIER1_ENTER | sender=%s | text=%s | business=%s | resolved_client_id=%r",
            sender_number,
            upper,
            business_number,
            resolved_client_id,
        )

        # -------------------------------------------------
        # HARD ORDER GUARD — NEVER TOUCH ORDER CONFIRMATION
        # -------------------------------------------------
        if upper in ("YES", "NO"):
            logger.info(
                "TIER1_BYPASS_ORDER_CONFIRM | sender=%s",
                sender_number,
            )
            return False

        # -------------------------------------------------
        # Admin path (fail closed)
        # -------------------------------------------------
        if business_number and is_admin_message(
            db=db,
            sender=sender_number,
            business_msisdn=business_number,
        ):
            logger.info(
                "TIER1_ROUTE_ADMIN | sender=%s | business=%s",
                sender_number,
                business_number,
            )
            return bool(
                handle_admin_command(
                    db=db,
                    sender_number=sender_number,
                    message_text=message_text,
                    msg=msg,
                    business_msisdn=business_number,
                )
            )

        # -------------------------------------------------
        # Customer path
        # -------------------------------------------------
        logger.info(
            "TIER1_ROUTE_CUSTOMER | sender=%s | business=%s",
            sender_number,
            business_number,
        )

        return bool(
            handle_customer_tier1(
                db=db,
                sender_number=sender_number,
                message_text=message_text,
                msg=msg,
                resolved_client_id=resolved_client_id,
                business_msisdn=business_number,
            )
        )

    except Exception as exc:
        logger.exception(
            "TIER1_ROUTER_FATAL | sender=%s | err=%s",
            sender_number,
            exc,
        )
        return True
