from __future__ import annotations

"""
File: app/clients/magen/workers/auto_close_worker.py
Path: app/clients/magen/workers/auto_close_worker.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Automatically close expired Magen inspections and trigger PDF generation.

Responsibilities (LOCKED):
- Detect ACTIVE inspections with no activity > AUTO_CLOSE_MINUTES
- Mark inspection as COMPLETED
- Trigger PDF generation once per inspection
- Log every step (no silent failures)

Notes:
- Safe to run on a schedule
- Idempotent per inspection
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.clients.magen.workers.pdf_worker import generate_and_send_inspection_pdf

logger = logging.getLogger("magen.auto_close")

AUTO_CLOSE_MINUTES = 5


def auto_close_expired_inspections(db: Session) -> None:
    logger.info("MAGEN_AUTO_CLOSE_START")

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

        if not rows:
            logger.info("MAGEN_AUTO_CLOSE_NONE")
            return

        logger.info(
            "MAGEN_AUTO_CLOSE_COUNT | closed=%s",
            len(rows),
        )

        for row in rows:
            inspection_id = row.inspection_id

            logger.info(
                "MAGEN_AUTO_CLOSE_TRIGGER_PDF | inspection_id=%s",
                inspection_id,
            )

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

    except Exception:
        logger.exception("MAGEN_AUTO_CLOSE_FATAL")
