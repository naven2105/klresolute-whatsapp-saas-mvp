from __future__ import annotations

"""
File: app/admin/magen_routes.py
Path: app/admin/magen_routes.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Admin-only, read-only endpoints for Magen inspections.

Rules (LOCKED):
- Read-only
- Backend-mediated access only
- PDFs streamed inline (no download by default)
- No presigned URLs
- No S3 exposure to browser
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import date

from app.db import get_db
from app.storage.s3_evidence_store import S3EvidenceStore

router = APIRouter(prefix="/admin/magen", tags=["admin", "magen"])

_s3_store = S3EvidenceStore()


# -------------------------------------------------------------------
# List inspections (read-only)
# -------------------------------------------------------------------
@router.get("/inspections")
def list_magen_inspections(
    db: Session = Depends(get_db),
):
    rows = db.execute(
        text(
            """
            SELECT
                inspection_id,
                officer_msisdn,
                status,
                started_at,
                completed_at
            FROM magen_inspections
            ORDER BY started_at DESC
            LIMIT 50
            """
        )
    ).mappings().all()

    return [
        {
            "inspection_id": r["inspection_id"],
            "officer_msisdn": r["officer_msisdn"],
            "status": r["status"],
            "started_at": r["started_at"],
            "completed_at": r["completed_at"],
            "report_url": f"/admin/magen/inspections/{r['inspection_id']}/report",
        }
        for r in rows
    ]


# -------------------------------------------------------------------
# View inspection PDF (inline)
# -------------------------------------------------------------------
@router.get("/inspections/{inspection_id}/report")
def view_inspection_report(
    inspection_id: int,
    db: Session = Depends(get_db),
):
    """
    Stream an inspection PDF to the browser (inline view).
    """

    inspection = db.execute(
        text(
            """
            SELECT inspection_id, completed_at
            FROM magen_inspections
            WHERE inspection_id = :id
            """
        ),
        {"id": inspection_id},
    ).mappings().first()

    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")

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

    try:
        stream = _s3_store.get_stream(key=s3_key)
    except Exception:
        raise HTTPException(
            status_code=404,
            detail="Inspection report not found",
        )

    return StreamingResponse(
        stream,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "inline; filename=inspection.pdf"
        },
    )
