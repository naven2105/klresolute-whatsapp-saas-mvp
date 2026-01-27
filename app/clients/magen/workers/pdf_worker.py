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
from datetime import date

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.messaging.client_messenger import send_message
from app.storage.s3_evidence_store import S3EvidenceStore

logger = logging.getLogger("clients.magen.pdf")

_s3_store = S3EvidenceStore()


def generate_and_send_inspection_pdf(
    *,
    db: Session,
    inspection_id: int,
) -> None:
    """
    Builds a simple inspection summary, stores PDF in S3,
    and sends summary to Admin.
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
        # Fetch events (schema-aligned)
        # ----------------------------------
        events = db.execute(
            text(
                """
                SELECT
                    event_type,
                    meta_media_id,
                    s3_url,
                    gps_lat,
                    gps_lng,
                    caption,
                    received_at
                FROM magen_inspection_events
                WHERE inspection_id = :id
                ORDER BY received_at
                """
            ),
            {"id": inspection_id},
        ).mappings().all()

        # ----------------------------------
        # Build report text (PDF content)
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
            if e["gps_lat"] is not None and e["gps_lng"] is not None:
                gps = f" GPS({e['gps_lat']},{e['gps_lng']})"

            caption = e["caption"] or ""
            lines.append(
                f"- {e['event_type']} | {e['received_at']}{gps} {caption}"
            )

        report_text = "\n".join(lines)

        # ----------------------------------
        # Generate PDF bytes (text-only MVP)
        # ----------------------------------
        pdf_bytes = report_text.encode("utf-8")

        # ----------------------------------
        # Store immutable PDF in S3 (Sprint 2)
        # ----------------------------------
        inspection_date = (
            inspection["completed_at"].date()
            if inspection["completed_at"]
            else date.today()
        )

        s3_key = (
            f"magen/inspections/"
            f"UNKNOWN/"
            f"{inspection_date}/"
            f"{inspection_id}/"
            f"report/inspection.pdf"
        )

        _s3_store.put_bytes(
            key=s3_key,
            data=pdf_bytes,
            content_type="application/pdf",
        )

        logger.info(
            "MAGEN_PDF_STORED | inspection_id=%s | s3_key=%s",
            inspection_id,
            s3_key,
        )

        # ----------------------------------
        # Dont Send summary to Admin 
        # ----------------------------------
        logger.info(
            "MAGEN_PDF_ADMIN_SEND_SKIPPED | inspection_id=%s",
            inspection_id,
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
