from __future__ import annotations

"""
File: app/modules/feedback/handler.py
Path: app/modules/feedback/handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Feedback module adapter.

Responsibilities (LOCKED):
- Delegate ALL feedback handling to existing feedback_handler
- No new business logic
- No DB schema changes
- Return True if feedback was handled
"""

import logging
from sqlalchemy.orm import Session

from app.handlers.feedback_handler import handle_feedback_message  # EXISTING, STABLE

logger = logging.getLogger("module.feedback")


def handle(
    *,
    db: Session,
    msg: dict,
    sender: str,
    business_msisdn: str,
) -> bool:
    """
    Feedback module entry point.
    """

    try:
        handled = handle_feedback_message(
            db=db,
            msg=msg,
            sender_number=sender,
            business_msisdn=business_msisdn,
        )

        if handled:
            logger.info(
                "FEEDBACK_HANDLED | sender=%s | business=%s",
                sender,
                business_msisdn,
            )

        return bool(handled)

    except Exception:
        logger.exception(
            "FEEDBACK_HANDLER_FAIL | sender=%s | business=%s",
            sender,
            business_msisdn,
        )
        return True  # swallow to protect webhook
