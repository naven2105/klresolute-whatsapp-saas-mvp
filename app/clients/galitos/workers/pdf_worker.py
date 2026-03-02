from __future__ import annotations

"""
File: app/clients/galitos/workers/pdf_worker.py
Path: app/clients/galitos/workers/pdf_worker.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Generate inspection PDF and send to Galitos Admin(s) via WhatsApp.

Rules (LOCKED):
- Read-only DB access
- One PDF per inspection
- DO NOT store PDF (no S3)
- Send ONLY to Galitos admins
- No inspection state changes here
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.messaging.client_messenger import send_message
from app.profiles.client_profile import get_client_profile

logger = logging.getLogger("clients.galitos.pdf")


def generate_and_send_inspection_pdf(
    *,
    db: Session,
    inspection_id: int,
) -> None:
    try:
        inspection = db.execute(
            text(
                """
                SELECT inspection_id,
                       officer_msisdn,
                       started_at,
                       completed_at,
                       business_msisdn
                FROM magen_inspections
                WHERE inspection_id = :id
                """
            ),
            {"id": inspection_id},
        ).mappings().first()

        if not inspection:
            logger.error("GALITOS_PDF_NO_INSPECTION | id=%s", inspection_id)
            return

        # ✅ FIX: pass db
        profile = get_client_profile(
            inspection["business_msisdn"],
            db=db,
        )

        if not profile or profile.client_id != "906a5084-1add-4b7a-bda0-90b462c9b8a9":
            logger.info(
                "GALITOS_PDF_SKIPPED_NON_GALITOS | id=%s | business=%s",
                inspection_id,
                inspection["business_msisdn"],
            )
            return

        admin_numbers = profile.admin_numbers or []
        if not admin_numbers:
            logger.warning("GALITOS_PDF_NO_ADMINS | id=%s", inspection_id)
            return

        events = db.execute(
            text(
                """
                SELECT
                    event_type,
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

        lines = [
            "Galitos Kitchen Inspection Report",
            "",
            f"Inspection ID: {inspection['inspection_id']}",
            f"Staff: {inspection['officer_msisdn']}",
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

        pdf_bytes = "\n".join(lines).encode("utf-8")
        filename = f"inspection_{inspection_id}.pdf"

        for admin_msisdn in admin_numbers:
            send_message(
                to_number=admin_msisdn,
                document_bytes=pdf_bytes,
                filename=filename,
            )

        logger.info(
            "GALITOS_PDF_SENT | inspection_id=%s | admins=%s | events=%s",
            inspection_id,
            len(admin_numbers),
            len(events),
        )

    except Exception:
        logger.exception(
            "GALITOS_PDF_FATAL | inspection_id=%s",
            inspection_id,
        )
