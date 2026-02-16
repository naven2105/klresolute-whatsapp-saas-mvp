from __future__ import annotations

"""
File: app/clients/magen/magen_media_handler.py
Path: app/clients/magen/magen_media_handler.py
Project: KLResolute WhatsApp SaaS MVP

Sprint: UUID Identity Consolidation

Purpose:
Handle Magen inspection image media and store immutable evidence in S3.

LOCKED RULES:
- Used only for Magen inspections
- Backend-only S3 access
- Immutable writes (write once)
- Keys are system-generated
- Business-scoped Meta sender identity required
"""

import logging
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.storage.s3_evidence_store import S3EvidenceStore
from app.outbound.factory import get_meta_client
from app.services.event_logger import log_event

logger = logging.getLogger("magen_media_handler")

_s3_store = S3EvidenceStore()


def _resolve_business_msisdn(db: Session, sender: str) -> str | None:
    """
    Resolve business number for this sender (Magen only).
    Assumes sender belongs to a mapped whatsapp_numbers record.
    """
    row = (
        db.execute(
            text(
                """
                SELECT w.destination_number
                FROM whatsapp_numbers w
                JOIN magen_staff s
                  ON s.client_id = w.client_id
                WHERE s.msisdn = :sender
                  AND w.status = 'active'
                LIMIT 1
                """
            ),
            {"sender": sender},
        )
        .mappings()
        .first()
    )

    if not row:
        logger.error(
            "MAGEN_MEDIA_BUSINESS_RESOLVE_FAIL | sender=%s",
            sender,
        )
        return None

    return row["destination_number"]


def handle_magen_inspection_media(
    *,
    db: Session,
    sender: str,
    media_id: str,
    mime_type: str,
    inspection_id: str,
    site_id: str,
    photo_index: int,
) -> None:
    """
    Handle a single inspection photo:
    - Download media bytes from Meta
    - Store immutably in S3
    - Log metadata only (no UX impact)
    """

    business_msisdn = _resolve_business_msisdn(db, sender)
    if not business_msisdn:
        return

    meta = get_meta_client(
        db=db,
        business_msisdn=business_msisdn,
    )

    logger.info(
        "MAGEN_MEDIA_ENTER | inspection_id=%s | media_id=%s | index=%s",
        inspection_id,
        media_id,
        photo_index,
    )

    # -------------------------------------------------
    # Download image bytes from Meta
    # -------------------------------------------------
    image_bytes = meta.download_media(media_id)

    # -------------------------------------------------
    # Build locked S3 key
    # -------------------------------------------------
    today = datetime.utcnow().strftime("%Y-%m-%d")
    filename = f"{photo_index:03d}.jpg"

    s3_key = (
        f"magen/inspections/"
        f"{site_id}/"
        f"{today}/"
        f"{inspection_id}/"
        f"photos/{filename}"
    )

    # -------------------------------------------------
    # Immutable write to S3
    # -------------------------------------------------
    _s3_store.put_bytes(
        key=s3_key,
        data=image_bytes,
        content_type=mime_type or "image/jpeg",
    )

    # -------------------------------------------------
    # Log event / metadata
    # -------------------------------------------------
    log_event(
        db=db,
        event_type="MAGEN_INSPECTION_PHOTO_STORED",
        actor_msisdn=sender,
        metadata={
            "inspection_id": inspection_id,
            "site_id": site_id,
            "s3_key": s3_key,
            "content_type": mime_type,
        },
    )

    logger.info(
        "MAGEN_MEDIA_STORED | inspection_id=%s | s3_key=%s",
        inspection_id,
        s3_key,
    )
