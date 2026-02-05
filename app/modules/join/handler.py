from __future__ import annotations

"""
File: app/modules/join/handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
ARCHIVED — JOIN is no longer used.
Customers are implicitly added on first interaction (Tier-1 router).
"""

import logging
from sqlalchemy.orm import Session

logger = logging.getLogger("module.join")


def handle(*, db: Session, msg: dict, sender: str, business_msisdn: str) -> bool:
    logger.info(
        "JOIN_HANDLER_ARCHIVED | sender=%s | business=%s",
        sender,
        business_msisdn,
    )
    return False
