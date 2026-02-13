from __future__ import annotations

"""
File: app/clients/magen/auto_close.py
Path: app/clients/magen/auto_close.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Auto-close stale Magen inspections after inactivity
and trigger PDF generation.

Rules (LOCKED):
- Only ACTIVE inspections
- Auto-close after 5 minutes of no events
- Update status + completed_at
- Trigger PDF worker per inspection
- No messaging here
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.clients.magen.inspection.workers.pdf_worker import (
    generate_and_send_inspection_pdf,
)

logger = logging.getLogger("clients.magen.auto_close")

AUTO_CLOSE_MINUTES = 5


def auto_close_expired_inspections(db: Session) -> int:
    """
    Auto-closes inspections and triggers PDF generation.

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

        closed_ids = [r.inspection_id for r in rows]

        if not closed_ids:
            logger.debug("MAGEN_AUTO_CLOSE_NONE")
            db.commit()
            return 0

        logger.info(
            "MAGEN_AUTO_CLOSE_SUCCESS | closed=%s",
            len(closed_ids),
        )

        db.commit()

        # ----------------------------------
        # Trigger PDF worker per inspection
        # ----------------------------------
        for inspection_id in closed_ids:
            try:
                generate_and_send_inspection_pdf(
                    db=db,
                    inspection_id=inspection_id,
                )
            except Exception:
                logger.exception(
                    "MAGEN_PDF_TRIGGER_FAIL | inspection_id=%s",
                    inspection_id,
                )

        return len(closed_ids)

    except Exception:
        db.rollback()
        logger.exception("MAGEN_AUTO_CLOSE_FATAL")
        return 0
