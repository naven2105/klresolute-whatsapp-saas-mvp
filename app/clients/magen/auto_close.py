from __future__ import annotations

"""
File: app/clients/magen/auto_close.py
Path: app/clients/magen/auto_close.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Auto-close stale Magen inspections after inactivity
and trigger PDF generation + delivery.

Rules (LOCKED):
- Only ACTIVE inspections
- Auto-close after 5 minutes of no events
- Update status + completed_at
- PDF generation is best-effort (never blocks auto-close)
- No WhatsApp messaging here
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.clients.magen.workers.pdf_worker import generate_and_send_inspection_pdf

logger = logging.getLogger("clients.magen.auto_close")

AUTO_CLOSE_MINUTES = 5


def auto_close_expired_inspections(db: Session) -> int:
    """
    Auto-close expired inspections and trigger PDF generation.

    Returns:
        Number of inspections auto-closed.
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

    except Exception:
        db.rollback()
        logger.exception("MAGEN_AUTO_CLOSE_FAIL")
        return 0

    # -------------------------------------------------
    # PDF generation (best-effort, never blocks)
    # -------------------------------------------------
    for row in rows:
        inspection_id = row.inspection_id
        try:
            generate_and_send_inspection_pdf(
                db=db,
                inspection_id=inspection_id,
            )
            logger.info(
                "MAGEN_PDF_TRIGGERED | inspection_id=%s",
                inspection_id,
            )
        except Exception:
            logger.exception(
                "MAGEN_PDF_TRIGGER_FAIL | inspection_id=%s",
                inspection_id,
            )

    return closed_count
