from __future__ import annotations

"""
File: app/clients/galitos/inbound.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Inbound entry point for Galitos WhatsApp number.

RULES:
- This file contains NO business logic
- Delegates immediately to existing Galitos handlers
- Exists to satisfy the unified dispatcher contract
"""

import logging
from sqlalchemy.orm import Session

from app.handlers.client_commands import handle_client_command

logger = logging.getLogger("clients.galitos")


def handle_inbound(
    *,
    db: Session,
    msg: dict,
    sender: str,
    business_msisdn: str,
) -> bool:
    """
    Returns True if Galitos logic handles the message.
    """

    try:
        handled = handle_client_command(
            db=db,
            sender_number=sender,
            message_text=(msg.get("text", {}) or {}).get("body", ""),
            msg=msg,
            resolved_client_id=None,
            resolved_business_number=business_msisdn,
        )

        if handled:
            logger.info(
                "GALITOS_INBOUND_HANDLED | sender=%s | business=%s",
                sender,
                business_msisdn,
            )
            return True

        return False

    except Exception:
        logger.exception(
            "GALITOS_INBOUND_FATAL | sender=%s | business=%s",
            sender,
            business_msisdn,
        )
        return True  # fail-safe: webhook must never crash
