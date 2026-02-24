from __future__ import annotations

"""
File: app/webhook_dedupe.py
Path: app/webhook_dedupe.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Provider message deduplication and replay protection.

Rules:
- Provider lock logic
- Message ID deduplication
- Replay protection
- No routing logic
"""

import logging

from sqlalchemy.orm import Session
from sqlalchemy import text


logger = logging.getLogger("webhooks")


def try_lock_provider_message(db: Session, provider_message_id: str) -> bool:
    if not provider_message_id:
        logger.warning("DEDUPE_SKIP | reason=no_provider_message_id")
        return True

    try:
        result = db.execute(
            text(
                """
                INSERT INTO inbound_message_dedupe (provider_message_id)
                VALUES (:pid)
                ON CONFLICT (provider_message_id) DO NOTHING
                """
            ),
            {"pid": provider_message_id},
        )
        db.commit()

        locked = bool(getattr(result, "rowcount", 0) == 1)

        logger.info(
            "DEDUPE_RESULT | pid=%s | locked=%s",
            provider_message_id,
            locked,
        )

        return locked

    except Exception:
        db.rollback()
        logger.exception("DEDUPE_LOCK_FAIL | pid=%s", provider_message_id)
        return True