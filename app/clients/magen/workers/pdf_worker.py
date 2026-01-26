from __future__ import annotations

"""
File: app/clients/magen/workers/pdf_worker.py
Path: app/clients/magen/workers/pdf_worker.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Generate a PDF inspection report for a completed Magen inspection
and send it to Admin WhatsApp number(s).

Responsibilities (LOCKED):
- Read inspection + events from DB
- Generate a PDF (single inspection)
- Send PDF to Admin(s)
- Log every step and failure

Notes:
- Called by auto_close_worker or explicit DONE command
- Must never crash the caller
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.outbound.meta import MetaWhatsAppClient
from app.outbound.settings import load_meta_settings

logger = logging.getLogger("magen.pdf_worker")

_meta = MetaWhatsAppClient(settings=load_meta_settings())


def generate_and_send_inspection_pdf(
    *,
    db: Session,
    inspection_id: int,
) -> None:
    logger.info(
        "MAGEN_PDF_START | inspection_id=%s",
        inspection_id,
    )

    try:
        # -------------------------------------------------
        # Load inspection header
        # -------------------------------------------------
        inspection = db.execute(
            text(
                """
                SELECT
                    i.inspection_id,
                    i.officer_msisdn,
                    i.status,
                    i.started_at,
                    i.completed_at
                FROM magen_inspections i
                WHERE i.inspection_id = :inspection_id
                """
            ),
            {"inspection_id": inspection_id},
        ).mappings().first()

        if not inspection:
            logger.error(
                "MAGEN_PDF_NO_INSPECTION | inspection_id=%s",
                inspection_id,
            )
            return

        # -------------------------------------------------
        # Load inspection events
        # -------------------------------------------------
        events = db.execute(
            text(
                """
                SELECT
                    event_type,
                    media_id,
                    latitude,
                    longitude,
                    caption,
                    created_at
                FROM magen_inspection_events
                WHERE inspection_id = :inspection_id
                ORDER BY created_at ASC
                """
            ),
            {"inspection_id": inspection_id},
        ).mappings().all()

        logger.info(
            "MAGEN_PDF_DATA_READY | inspection_id=%s | events=%s",
            inspection_id,
            len(events),
        )

        # -------------------------------------------------
        # PDF generation (placeholder – deterministic)
        # -------------------------------------------------
        # NOTE:
        # For now we generate a simple text-based PDF payload.
        # Actual PDF rendering (ReportLab) can replace this later
        # without touching callers.

        pdf_bytes = (
            f"Magen Inspection Report\n\n"
            f"Inspection ID: {inspection['inspection_id']}\n"
            f"Officer: {inspection['officer_msisdn']}\n"
            f"Status: {inspection['status']}\n"
            f"Started: {inspection['started_at']}\n"
            f"Completed: {inspection['completed_at']}\n\n"
            f"Events:\n"
        ).encode("utf-8")

        for e in events:
            line = (
                f"- {e['created_at']} | {e['event_type']} | "
                f"{e.get('caption') or ''} "
                f"{f'GPS({e['latitude']},{e['longitude']})' if e['latitude'] else ''}\n"
            )
            pdf_bytes += line.encode("utf-8")

        # -------------------------------------------------
        # Resolve Admin recipients
        # -------------------------------------------------
        admins = db.execute(
            text(
                """
                SELECT msisdn
                FROM klresolute_admin
                WHERE is_active = TRUE
                """
            )
        ).fetchall()

        if not admins:
            logger.warning("MAGEN_PDF_NO_ADMINS")
            return

        # -------------------------------------------------
        # Send PDF to Admin(s)
        # -------------------------------------------------
        for admin in admins:
            try:
                _meta.send_document_message(
                    to_msisdn=admin.msisdn,
                    filename=f"inspection_{inspection_id}.pdf",
                    file_bytes=pdf_bytes,
                    caption="Magen Security Inspection Report",
                )

                logger.info(
                    "MAGEN_PDF_SENT | inspection_id=%s | admin=%s",
                    inspection_id,
                    admin.msisdn,
                )

            except Exception:
                logger.exception(
                    "MAGEN_PDF_SEND_FAIL | inspection_id=%s | admin=%s",
                    inspection_id,
                    admin.msisdn,
                )

    except Exception:
        logger.exception(
            "MAGEN_PDF_FATAL | inspection_id=%s",
            inspection_id,
        )
