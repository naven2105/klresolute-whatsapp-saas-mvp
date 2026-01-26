from __future__ import annotations

"""
File: app/clients/magen/workers/pdf_worker.py
Path: app/clients/magen/workers/pdf_worker.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Generate inspection PDF and send to Admin.

Rules (LOCKED):
- Read-only DB access
- One PDF per inspection
- No inspection state changes here
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.messaging.client_messenger import send_message

logger = logging.getLogger("clients.magen.pdf")


def generate_and_send_inspection_pdf(
    *,
    db: Session,
    inspection_id: int,
) -> None:
    """
    Builds a simple inspection summary and sends to Admin.
    """

    try:
        # ----------------------------------
        # Fetch inspection header
        # ----------------------------------
        inspection = db.execute(
            text(
                """
                SELECT inspection_id, officer_msisdn, started_at, completed_at
                FROM magen_inspections
                WHERE inspection_id = :id
                """
            ),
            {"id": inspection_id},
        ).mappings().first()

        if not inspection:
            logger.error(
                "MAGEN_PDF_NO_INSPECTION | id=%s",
                inspection_id,
            )
            return

        # ----------------------------------
        # Fetch events
        # ----------------------------------
        events = db.execute(
            text(
                """
                SELECT event_type, media_id, latitude, longitude, caption, created_at
                FROM magen_inspection_events
                WHERE inspection_id = :id
                ORDER BY created_at
                """
            ),
            {"id": inspection_id},
        ).mappings().all()

        # ----------------------------------
        # Build text (NO f-string nesting)
        # ----------------------------------
        lines = [
            "Magen Security Inspection Report",
            "",
            f"Inspection ID: {inspection['inspection_id']}",
            f"Officer: {inspection['officer_msisdn']}",
            f"Started: {inspection['started_at']}",
            f"Completed: {inspection['completed_at']}",
            "",
            "Events:",
        ]

        for e in events:
            gps = ""
            if e["latitude"] is not None and e["longitude"] is not None:
                gps = f" GPS({e['latitude']},{e['longitude']})"

            caption = e["caption"] or ""
            lines.append(
                f"- {e['event_type']} | {e['created_at']}{gps} {caption}"
            )

        report_text = "\n".join(lines)

        # ----------------------------------
        # Send to Admin (text for now)
        # ----------------------------------
        send_message(
            to_number="ADMIN",  # existing routing
            text=report_text,
        )

        logger.info(
            "MAGEN_PDF_SENT | inspection_id=%s | events=%s",
            inspection_id,
            len(events),
        )

    except Exception:
        logger.exception(
            "MAGEN_PDF_FATAL | inspection_id=%s",
            inspection_id,
        )
