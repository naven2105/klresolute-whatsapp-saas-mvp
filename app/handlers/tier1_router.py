from __future__ import annotations

"""
File: app/handlers/tier1_router.py
Path: app/handlers/tier1_router.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Tier-1 orchestration only.
"""

import logging
from sqlalchemy.orm import Session

from app.utils.admin import is_admin_message
from app.handlers.tier1_customer_entry import handle_customer_entry
from app.handlers.tier1_admin_entry import handle_admin_entry

logger = logging.getLogger("handlers.tier1.router")


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
    upper = (message_text or "").strip().upper()

    if upper in ("YES", "NO"):
        return False

    business = resolved_business_number

    is_admin = (
        business
        and is_admin_message(
            db=db,
            sender=sender_number,
            business_msisdn=business,
        )
    )

    if is_admin:
        return handle_admin_entry(
            db=db,
            sender_number=sender_number,
            message_text=message_text,
            msg=msg,
            business_msisdn=business,
        )

    return handle_customer_entry(
        db=db,
        sender_number=sender_number,
        message_text=message_text,
        msg=msg,
        resolved_client_id=resolved_client_id,
        business_msisdn=business,
    )
