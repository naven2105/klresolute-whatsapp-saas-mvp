from __future__ import annotations

"""
File: app/clients/magen/auto_close.py
Path: app/clients/magen/auto_close.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Auto-close stale Magen inspections after inactivity.

Rules (LOCKED):
- Only ACTIVE inspections
- Auto-close after 5 minutes of no events
- Update status + completed_at
- No messaging
- No PDF generation here
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger("clients.magen.auto_close")

AUTO_CLOSE_MINUTES = 5


def auto_close_expired_inspections(db: Session) -> int:
    """
    Returns number of inspections auto-closed.
    """

    try:
        rows = db.execute(
            text(
                """
                UPDATE magen_inspections
                SET status = 'AUTO_CLOSED',
                    completed_at = now()
                WHERE status = 'ACTIVE'
                  AND last_event_at < now() - interval '5 minutes'
                RETURNING inspection_id
                """
            )
        ).fetchall()

        closed_count = len(rows)

        if closed_count:
            logger.info(
                "MAGEN_AUTO_CLOSE_SUCCESS | closed=%s",
                closed_count,
            )
        else:
            logger.debug("MAGEN_AUTO_CLOSE_NONE")

        db.commit()
        return closed_count

    except Exception:
        db.rollback()
        logger.exception("MAGEN_AUTO_CLOSE_FAIL")
        return 0
