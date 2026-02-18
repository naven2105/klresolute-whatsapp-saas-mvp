from __future__ import annotations

"""
File: app/clients/magen/admin/routes.py
Path: app/clients/magen/admin/routes.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Magen-specific Lite Admin Portal.

Features:
- Date filter
- Closed inspections ONLY where PDF generated
- Officer full name display
- SAST timestamp display
- Immutable PDF download (signed URL)
- Structured logging + guard rails
"""

import logging
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import text

from app.db import SessionLocal
from app.storage.s3_evidence_store import S3EvidenceStore

router = APIRouter()
logger = logging.getLogger("clients.magen.admin")
SAST = ZoneInfo("Africa/Johannesburg")


# -------------------------------------------------
# Inspection List
# -------------------------------------------------

@router.get("/admin/magen/inspections", response_class=HTMLResponse)
def list_inspections(
    request: Request,
    from_date: str | None = None,
    to_date: str | None = None,
):

    logger.info(
        "MAGEN_ADMIN_LIST_REQUEST | from=%s | to=%s",
        from_date,
        to_date,
    )

    db = SessionLocal()

    try:
        query = """
            SELECT i.inspection_id,
                   i.officer_msisdn,
                   s.full_name,
                   i.completed_at,
                   i.status
            FROM magen_inspections i
            LEFT JOIN magen_staff s
                ON s.msisdn = i.officer_msisdn
            WHERE i.status = 'CLOSED'
              AND i.pdf_generated = TRUE
        """

        params: dict = {}

        if from_date:
            query += " AND i.completed_at >= :from_date"
            params["from_date"] = from_date

        if to_date:
            query += " AND i.completed_at <= :to_date"
            params["to_date"] = to_date + " 23:59:59"

        query += " ORDER BY i.completed_at DESC"

        rows = db.execute(text(query), params).mappings().all()

        logger.info(
            "MAGEN_ADMIN_LIST_RESULT | count=%s",
            len(rows),
        )

    except Exception:
        logger.exception("MAGEN_ADMIN_LIST_ERROR")
        return HTMLResponse(
            content="<h3>Internal Error</h3>",
            status_code=500,
        )
    finally:
        db.close()

    html = """
    <html>
    <head>
        <title>Magen Inspections</title>
    </head>
    <body>
        <h2>Magen Inspection Reports</h2>

        <form method="get">
            From: <input type="date" name="from_date">
            To: <input type="date" name="to_date">
            <button type="submit">Search</button>
        </form>

        <br><br>

        <table border="1" cellpadding="8">
            <tr>
                <th>Inspection ID</th>
                <th>Officer Name</th>
                <th>Officer Mobile</th>
                <th>Completed (SAST)</th>
                <th>Status</th>
                <th>PDF</th>
            </tr>
    """

    for r in rows:
        completed = r["completed_at"]

        completed_sast = (
            completed.astimezone(SAST)
            .strftime("%Y-%m-%d %H:%M:%S")
            if completed else "N/A"
        )

        html += f"""
            <tr>
                <td>{r["inspection_id"]}</td>
                <td>{r["full_name"] or "Unknown"}</td>
                <td>{r["officer_msisdn"]}</td>
                <td>{completed_sast}</td>
                <td>{r["status"]}</td>
                <td>
                    <a href="/admin/magen/inspections/{r["inspection_id"]}/download">
                        Download
                    </a>
                </td>
            </tr>
        """

    html += """
        </table>
    </body>
    </html>
    """

    return HTMLResponse(content=html)


# -------------------------------------------------
# Download PDF
# -------------------------------------------------

@router.get("/admin/magen/inspections/{inspection_id}/download")
def download_pdf(inspection_id: str):

    logger.info(
        "MAGEN_ADMIN_DOWNLOAD_REQUEST | inspection_id=%s",
        inspection_id,
    )

    db = SessionLocal()

    try:
        row = db.execute(
            text(
                """
                SELECT pdf_s3_key
                FROM magen_inspections
                WHERE inspection_id = :id
                  AND pdf_generated = TRUE
                """
            ),
            {"id": inspection_id},
        ).mappings().first()

        if not row or not row["pdf_s3_key"]:
            logger.warning(
                "MAGEN_ADMIN_DOWNLOAD_NOT_FOUND | inspection_id=%s",
                inspection_id,
            )
            return HTMLResponse(
                content="<h3>PDF not available</h3>",
                status_code=404,
            )

        s3 = S3EvidenceStore()

        try:
            signed_url = s3.generate_signed_url(row["pdf_s3_key"])
        except Exception:
            logger.exception(
                "MAGEN_ADMIN_SIGNED_URL_FAIL | inspection_id=%s",
                inspection_id,
            )
            return HTMLResponse(
                content="<h3>S3 Error</h3>",
                status_code=500,
            )

        logger.info(
            "MAGEN_ADMIN_DOWNLOAD_REDIRECT | inspection_id=%s",
            inspection_id,
        )

        return RedirectResponse(url=signed_url)

    except Exception:
        logger.exception(
            "MAGEN_ADMIN_DOWNLOAD_ERROR | inspection_id=%s",
            inspection_id,
        )
        return HTMLResponse(
            content="<h3>Internal Error</h3>",
            status_code=500,
        )
    finally:
        db.close()
