from __future__ import annotations

"""
File: app/modules/feedback/handler.py
Path: app/modules/feedback/handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Stub handler for Feedback module.

Responsibilities (LOCKED):
- Claim feedback-related messages (future)
- Return False for now so other modules can handle
- NO DB writes
- NO outbound messaging
"""

import logging
from sqlalchemy.orm import Session

logger = logging.getLogger("module.feedback")


def handle(
    *,
    db: Session,
    msg: dict,
    sender: str,
    business_msisdn: str,
) -> bool:
    """
    Feedback module stub.
    """

    # Not implemented yet — do not consume messages
    return False
