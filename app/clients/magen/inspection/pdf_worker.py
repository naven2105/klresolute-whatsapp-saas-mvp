from __future__ import annotations

"""
File: app/clients/magen/inspection/pdf_worker.py
Path: app/clients/magen/inspection/pdf_worker.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Generate immutable inspection PDF (4 photos per page) and store in S3.

Rules (LOCKED):
- One PDF per inspection (no regeneration)
- Do NOT modify inspection lifecycle
- Must update pdf_s3_key + pdf_generated flags
- Clean professional black/white layout
- Display timestamps in SAST (Africa/Johannesburg)
"""

import logging
import io
from datetime import date
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session
from sqlalchemy import text

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

from app.storage.s3_evidence_store import S3EvidenceStore

logger = logging.getLogger("clients.magen.pdf")

_s3_store = S3EvidenceStore()
SAST = ZoneInfo("Africa/Johannesburg")


def generate_and_send_inspection_pdf(
    *,
    db: Session,
    inspection_id: str,
) -> None:

    try:
        # -------------------------------------------------
        # Check if PDF already generated
        # -------------------------------------------------
        existing = db.execute(
            text(
                """
                SELECT pdf_generated, pdf_s3_key
                FROM magen_inspections
                WHERE inspection_id = :id
                """
            ),
            {"id": inspection_id},
        ).mappings().first()

        if not existing:
            logger.error("MAGEN_PDF_NO_INSPECTION | id=%s", inspection_id)
            return

        if existing["pdf_generated"]:
            logger.info(
                "MAGEN_PDF_ALREADY_GENERATED | id=%s | key=%s",
                inspection_id,
                existing["pdf_s3_key"],
            )
            return

        # -------------------------------------------------
        # Fetch inspection header + officer name
        # -------------------------------------------------
        inspection = db.execute(
            text(
                """
                SELECT i.inspection_id,
                       i.officer_msisdn,
                       i.started_at,
                       i.completed_at,
                       i.closed_reason,
                       s.full_name
                FROM magen_inspections i
                LEFT JOIN magen_staff s
                    ON s.msisdn = i.officer_msisdn
                WHERE i.inspection_id = :id
                """
            ),
            {"id": inspection_id},
        ).mappings().first()

        if not inspection:
            logger.error("MAGEN_PDF_HEADER_NOT_FOUND | id=%s", inspection_id)
            return

        # -------------------------------------------------
        # Fetch PHOTO events
        # -------------------------------------------------
        photos = db.execute(
            text(
                """
                SELECT
                    s3_url,
                    gps_lat,
                    gps_lng,
                    caption,
                    received_at
                FROM magen_inspection_events
                WHERE inspection_id = :id
                  AND event_type = 'PHOTO'
                ORDER BY received_at
                """
            ),
            {"id": inspection_id},
        ).mappings().all()

        # -------------------------------------------------
        # Convert header timestamps to SAST
        # -------------------------------------------------
        started_sast = inspection["started_at"].astimezone(SAST)
        completed_sast = (
            inspection["completed_at"].astimezone(SAST)
            if inspection["completed_at"]
            else None
        )

        # -------------------------------------------------
        # Create PDF
        # -------------------------------------------------
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        # ---------------- HEADER PAGE ----------------
        c.setFont("Helvetica-Bold", 16)
        c.drawString(
            30 * mm,
            height - 30 * mm,
            "MAGEN SECURITY – INSPECTION REPORT",
        )

        c.setFont("Helvetica", 11)
        y = height - 45 * mm

        def line(label: str, value: str):
            nonlocal y
            c.drawString(30 * mm, y, f"{label}: {value}")
            y -= 8 * mm

        line("Inspection ID", str(inspection["inspection_id"]))
        line("Officer Name", inspection["full_name"] or "Unknown")
        line("Officer Mobile", inspection["officer_msisdn"])
        line("Started (SAST)", started_sast.strftime("%Y-%m-%d %H:%M:%S"))
        line(
            "Completed (SAST)",
            completed_sast.strftime("%Y-%m-%d %H:%M:%S")
            if completed_sast
            else "N/A",
        )
        line("Closed Reason", inspection["closed_reason"] or "N/A")

        c.showPage()

        # ---------------- PHOTO PAGES ----------------
        photos_per_page = 4
        col_width = (width - 40 * mm) / 2
        row_height = (height - 40 * mm) / 2

        x_positions = [20 * mm, 20 * mm + col_width]
        y_positions = [
            height - 20 * mm - row_height,
            height - 20 * mm - (row_height * 2),
        ]

        index = 0

        for photo in photos:

            if index % photos_per_page == 0:
                if index != 0:
                    c.showPage()

            slot = index % photos_per_page
            col = slot % 2
            row = slot // 2

            x = x_positions[col]
            y = y_positions[row]

            try:
                image_bytes = _s3_store.get_bytes(photo["s3_url"])
                img = ImageReader(io.BytesIO(image_bytes))

                c.drawImage(
                    img,
                    x,
                    y + 25,
                    width=col_width - 10,
                    height=row_height - 40,
                    preserveAspectRatio=True,
                    anchor="c",
                )
            except Exception:
                logger.exception(
                    "MAGEN_PDF_IMAGE_FETCH_FAIL | id=%s | key=%s",
                    inspection_id,
                    photo["s3_url"],
                )

            # Convert timestamp to SAST
            received_sast = photo["received_at"].astimezone(SAST)

            if photo["gps_lat"] is not None and photo["gps_lng"] is not None:
                gps = f"{photo['gps_lat']}, {photo['gps_lng']}"
            else:
                gps = "NOT CAPTURED"

            caption = photo["caption"] or ""

            c.setFont("Helvetica", 9)
            c.drawString(
                x,
                y + 15,
                f"Time (SAST): {received_sast.strftime('%Y-%m-%d %H:%M:%S')}",
            )
            c.drawString(x, y + 7, f"GPS: {gps}")
            c.drawString(x, y - 1, caption)

            index += 1

        c.save()
        pdf_bytes = buffer.getvalue()

        # -------------------------------------------------
        # Store PDF in S3
        # -------------------------------------------------
        inspection_date = (
            completed_sast.date() if completed_sast else date.today()
        )

        s3_key = (
            f"magen/inspections/UNKNOWN/"
            f"{inspection_date}/"
            f"{inspection_id}/report/inspection.pdf"
        )

        _s3_store.put_bytes(
            key=s3_key,
            data=pdf_bytes,
            content_type="application/pdf",
        )

        # -------------------------------------------------
        # Update inspection record
        # -------------------------------------------------
        db.execute(
            text(
                """
                UPDATE magen_inspections
                SET pdf_s3_key = :key,
                    pdf_generated = TRUE,
                    pdf_generated_at = now()
                WHERE inspection_id = :id
                """
            ),
            {"key": s3_key, "id": inspection_id},
        )
        db.commit()

        logger.info(
            "MAGEN_PDF_GENERATED_SUCCESS | inspection_id=%s | s3_key=%s",
            inspection_id,
            s3_key,
        )

    except Exception:
        db.rollback()
        logger.exception(
            "MAGEN_PDF_FATAL | inspection_id=%s",
            inspection_id,
        )
