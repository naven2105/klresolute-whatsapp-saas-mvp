from __future__ import annotations

"""
File: app/magen/auto_close.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Auto-close expired Magen security inspections.

Behaviour (LOCKED):
- Finds ACTIVE inspections with no activity for AUTO_CLOSE_MINUTES
- Marks them COMPLETED
- Sets completed_at timestamp
- Logs count of auto-closed inspections
- Never raises to caller (fail-safe)
"""

from sqlalchemy.orm import Session
from sqlalchemy import text
import logging

logger = logging.getLogger("magen.auto_close")

AUTO_CLOSE_MINUTES = 5


def auto_close_expired_inspections(db: Session):
    try:
        rows = db.execute(
            text(
                """
                UPDATE magen_inspections
                SET status = 'COMPLETED',
                    completed_at = now()
                WHERE status = 'ACTIVE'
                  AND last_event_at < now() - interval '5 minutes'
                RETURNING inspection_id
                """
            )
        ).fetchall()

        if rows:
            logger.info(
                "MAGEN_AUTO_CLOSE | closed=%s",
                len(rows),
            )

    except Exception as e:
        logger.exception(
            "MAGEN_AUTO_CLOSE_FAILED | err=%s",
            str(e),
        )
