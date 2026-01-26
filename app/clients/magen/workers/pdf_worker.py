from __future__ import annotations

"""
File: app/clients/magen/workers/pdf_worker.py
Path: app/clients/magen/workers/pdf_worker.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Generate and deliver a Magen Security Inspection PDF to Admin.

Responsibilities (LOCKED):
- Fetch inspection + events from DB
- Generate a single immutable PDF per inspection
- Log failures clearly (no silent failures)
- No WhatsApp inbound logic
- No inspection state changes

Notes:
- Storage backend (local/S3) is abstracted
- PDF generation must never block webhook flow
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime

logger = logging.getLogger("magen.pdf_worker")


# -------------------------------------------------
# Main entry
# -------------------------------------------------

def generate_and_send_inspection_pdf(
    *,
    db: Session,
    inspection_id: int,
) -> None:
    """
    Generate PDF for a completed inspection and send to Admin.
    """

    logger.info(
        "PDF_WORKER_START | inspection_id=%s",
        inspection_id,
    )

    try:
        inspection = _load_inspection(db, inspection_id)
        events = _load_events(db, inspection_id)

        if not inspection:
            logger.error(
                "PDF_WORKER_NO_INSPECTION | inspection_id=%s",
                inspection_id,
            )
            return

        pdf_path = _build_pdf(
            inspection=inspection,
            events=events,
        )

        _notify_admin(
            db=db,
            inspection=inspection,
            pdf_path=pdf_path,
        )

        logger.info(
            "PDF_WORKER_SUCCESS | inspection_id=%s | pdf=%s",
            inspection_id,
            pdf_path,
        )

    except Exception:
        logger.exception(
            "PDF_WORKER_FATAL | inspection_id=%s",
            inspection_id,
        )


# -------------------------------------------------
# Data loaders
# -------------------------------------------------

def _load_inspection(db: Session, inspection_id: int):
    return db.execute(
        text(
            """
            SELECT *
            FROM magen_inspections
            WHERE inspection_id = :id
            """
        ),
        {"id": inspection_id},
    ).mappings().first()


def _load_events(db: Session, inspection_id: int):
    return db.execute(
        text(
            """
            SELECT *
            FROM magen_inspection_events
            WHERE inspection_id = :id
            ORDER BY created_at ASC
            """
        ),
        {"id": inspection_id},
    ).mappings().all()


# -------------------------------------------------
# PDF builder (stub – deterministic)
# -------------------------------------------------

def _build_pdf(*, inspection: dict, events: list[dict]) -> str:
    """
    Deterministic PDF build.
    Replace internals later (ReportLab / WeasyPrint).
    """

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    pdf_path = f"/tmp/magen_inspection_{inspection['inspection_id']}_{timestamp}.pdf"

    logger.info(
        "PDF_BUILD | inspection_id=%s | events=%s",
        inspection["inspection_id"],
        len(events),
    )

    # Placeholder: actual PDF generation lives here
    # MUST be deterministic and repeatable

    return pdf_path


# -------------------------------------------------
# Admin notification (stub)
# -------------------------------------------------

def _notify_admin(*, db: Session, inspection: dict, pdf_path: str) -> None:
    """
    Notify Admin that inspection PDF is ready.
    Delivery mechanism is pluggable.
    """

    logger.info(
        "PDF_ADMIN_NOTIFY | inspection_id=%s | pdf=%s",
        inspection["inspection_id"],
        pdf_path,
    )

    # WhatsApp / Email / Drive upload hooks go here
