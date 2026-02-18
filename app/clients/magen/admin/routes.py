from __future__ import annotations

"""
File: app/clients/magen/admin/routes.py
Path: app/clients/magen/admin/routes.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Magen-specific Lite Admin Portal.

Features:
- Date filter (closed inspections only)
- SAST timestamp display
- Immutable PDF download (signed URL)
- Structured logging
- Guard rails (no silent failures)
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
            SELECT inspection_id,
                   officer_msisdn,
                   completed_at,
                   status,
                   pdf_generated
            FROM magen_inspections
            WHERE status = 'CLOSED'
        """

        params: dict = {}

        if from_date:
            query += " AND completed_at >= :from_date"
            params["from_date"] = from_date

        if to_date:
            query += " AND completed_at <= :to_date"
            params["to_date"] = to_date + " 23:59:59"

        query += " ORDER BY completed_at DESC"

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
                <th>Officer</th>
                <th>Completed (SAST)</th>
                <th>Status</th>
                <th>PDF</th>
            </tr>
    """

    for r in rows:
        completed = r["completed_at"]
        if completed:
            completed_sast = (
                completed.astimezone(SAST)
                .strftime("%Y-%m-%d %H:%M:%S")
            )
        else:
            completed_sast = "N/A"

        if r["pdf_generated"]:
            download_link = (
                f'<a href="/admin/magen/inspections/{r["inspection_id"]}/download">'
                f'Download</a>'
            )
        else:
            download_link = "Not generated"

        html += f"""
            <tr>
                <td>{r["inspection_id"]}</td>
                <td>{r["officer_msisdn"]}</td>
                <td>{completed_sast}</td>
                <td>{r["status"]}</td>
                <td>{download_link}</td>
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
        signed_url = s3.generate_signed_url(row["pdf_s3_key"])

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
