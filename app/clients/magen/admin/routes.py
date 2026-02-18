from __future__ import annotations

"""
File: app/clients/magen/admin/routes.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Magen-specific Lite Admin Portal.

- Date filter
- Officer full name
- SAST timestamps
- Backend-streamed PDF (no presigned URLs)
- Client-isolated storage
"""

import logging
from datetime import date
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy import text

from app.db import SessionLocal
from app.clients.magen.storage.s3_store import S3EvidenceStore

router = APIRouter()
logger = logging.getLogger("clients.magen.admin")
SAST = ZoneInfo("Africa/Johannesburg")

_s3 = S3EvidenceStore()


# -------------------------------------------------
# Inspection List
# -------------------------------------------------

@router.get("/admin/magen/inspections", response_class=HTMLResponse)
def list_inspections(
    request: Request,
    from_date: str | None = None,
    to_date: str | None = None,
):

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

    except Exception:
        logger.exception("MAGEN_ADMIN_LIST_ERROR")
        return HTMLResponse("<h3>Internal Error</h3>", status_code=500)
    finally:
        db.close()

    html = """
    <html>
    <head><title>Magen Inspections</title></head>
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
                    <a href="/admin/magen/inspections/{r["inspection_id"]}/report">
                        View
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
# Stream PDF Inline
# -------------------------------------------------

@router.get("/admin/magen/inspections/{inspection_id}/report")
def stream_pdf(inspection_id: str):

    db = SessionLocal()

    try:
        inspection = db.execute(
            text(
                """
                SELECT inspection_id,
                       completed_at,
                       pdf_s3_key
                FROM magen_inspections
                WHERE inspection_id = :id
                  AND pdf_generated = TRUE
                """
            ),
            {"id": inspection_id},
        ).mappings().first()

        if not inspection:
            raise HTTPException(status_code=404, detail="Inspection not found")

        s3_key = inspection["pdf_s3_key"]

        stream = _s3.get_stream(key=s3_key)

        return StreamingResponse(
            stream,
            media_type="application/pdf",
            headers={
                "Content-Disposition": "inline; filename=inspection.pdf"
            },
        )

    except HTTPException:
        raise
    except Exception:
        logger.exception("MAGEN_ADMIN_STREAM_ERROR | id=%s", inspection_id)
        raise HTTPException(status_code=500, detail="S3 Error")
    finally:
        db.close()
