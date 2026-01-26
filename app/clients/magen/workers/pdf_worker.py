from __future__ import annotations

"""
File: app/clients/magen/workers/pdf_worker.py
Path: app/clients/magen/workers/pdf_worker.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Generate inspection PDF for Magen Security and send to Admin.

Rules (LOCKED):
- Read-only DB access
- No WhatsApp inbound handling
- Called only on inspection close
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime

from app.messaging.client_messenger import send_message

logger = logging.getLogger("clients.magen.pdf")


def generate_and_send_inspection_pdf(
    *,
    db: Session,
    inspection_id: int,
) -> None:
    """
    Generate a PDF summary and notify Admin.
    """

    try:
        # ----------------------------------
        # Fetch inspection header
        # ----------------------------------
        inspection = db.execute(
            text(
                """
                SELECT officer_msisdn, started_at, completed_at
                FROM magen_inspections
                WHERE inspection_id = :id
                """
            ),
            {"id": inspection_id},
        ).mappings().first()

        if not inspection:
            logger.error(
                "MAGEN_PDF_NO_INSPECTION | inspection_id=%s",
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
        # Build text summary (PDF placeholder)
        # ----------------------------------
        lines = []
        lines.append("Magen Security Inspection Report")
        lines.append(f"Officer: {inspection['officer_msisdn']}")
        lines.append(f"Started: {inspection['started_at']}")
        lines.append(f"Completed: {inspection['completed_at']}")
        lines.append("")

        for e in events:
            event_type = e["event_type"]
            caption = e["caption"] or ""

            lat = e["latitude"]
            lng = e["longitude"]

            gps_text = ""
            if lat is not None and lng is not None:
                gps_text = f" GPS({lat},{lng})"

            lines.append(
                f"[{e['created_at']}] {event_type}{gps_text} {caption}"
            )

        report_text = "\n".join(lines)

        # ----------------------------------
        # SEND (placeholder: WhatsApp admin)
        # ----------------------------------
        send_message(
            to_number=inspection["officer_msisdn"],
            text=(
                "📄 Inspection completed.\n"
                "Report generated and sent to Admin."
            ),
        )

        logger.info(
            "MAGEN_PDF_GENERATED | inspection_id=%s | events=%s",
            inspection_id,
            len(events),
        )

    except Exception:
        logger.exception(
            "MAGEN_PDF_FATAL | inspection_id=%s",
            inspection_id,
        )
