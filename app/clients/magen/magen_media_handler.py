from __future__ import annotations

"""
File: app/clients/magen/magen_media_handler.py
Path: app/clients/magen/magen_media_handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Handle Magen inspection image media and store immutable evidence in S3.

LOCKED RULES:
- Used only for Magen inspections
- Backend-only S3 access
- Immutable writes (write once)
- Keys are system-generated
- No admin / specials / broadcast logic here
- Business-scoped Meta sender identity required
- Event logging must use UUID client_id
"""

import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.storage.s3_evidence_store import S3EvidenceStore
from app.outbound.factory import get_meta_client
from app.services.event_logger import log_event

logger = logging.getLogger("magen_media_handler")

_s3_store = S3EvidenceStore()


def _resolve_business_msisdn(db: Session, sender: str) -> str | None:
    row = (
        db.execute(
            text(
                """
                SELECT w.destination_number
                FROM whatsapp_numbers w
                JOIN clients c ON c.client_id = w.client_id
                WHERE w.status = 'active'
                LIMIT 1
                """
            )
        )
        .mappings()
        .first()
    )

    if not row:
        logger.error("MAGEN_MEDIA_BUSINESS_RESOLVE_FAIL | sender=%s", sender)
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
    Handle a single inspection photo.
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
    # Download media
    # -------------------------------------------------
    try:
        image_bytes = meta.download_media(media_id)
        if not image_bytes:
            raise RuntimeError("Meta returned empty media bytes")

        logger.info(
            "MAGEN_MEDIA_DOWNLOAD_OK | inspection_id=%s | bytes=%s",
            inspection_id,
            len(image_bytes),
        )
    except Exception:
        logger.exception(
            "MAGEN_MEDIA_DOWNLOAD_FAIL | inspection_id=%s | media_id=%s",
            inspection_id,
            media_id,
        )
        raise

    # -------------------------------------------------
    # Build S3 key
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
    # Upload to S3
    # -------------------------------------------------
    try:
        _s3_store.put_bytes(
            key=s3_key,
            data=image_bytes,
            content_type=mime_type or "image/jpeg",
        )

        logger.info(
            "MAGEN_MEDIA_UPLOAD_OK | inspection_id=%s | s3_key=%s",
            inspection_id,
            s3_key,
        )
    except Exception:
        logger.exception(
            "MAGEN_MEDIA_UPLOAD_FAIL | inspection_id=%s",
            inspection_id,
        )
        raise

    # -------------------------------------------------
    # Link S3 key to inspection event
    # -------------------------------------------------
    try:
        result = db.execute(
            text(
                """
                UPDATE magen_inspection_events
                SET s3_url = :s3_key
                WHERE inspection_id = :inspection_id
                  AND event_type = 'PHOTO'
                  AND meta_media_id = :media_id
                  AND s3_url IS NULL
                """
            ),
            {
                "s3_key": s3_key,
                "inspection_id": inspection_id,
                "media_id": media_id,
            },
        )

        if result.rowcount != 1:
            db.rollback()
            logger.error(
                "MAGEN_MEDIA_DB_LINK_FAIL | inspection_id=%s | rowcount=%s",
                inspection_id,
                result.rowcount,
            )
            raise RuntimeError("PHOTO event linkage failed")

        db.commit()

        logger.info(
            "MAGEN_MEDIA_DB_LINK_OK | inspection_id=%s",
            inspection_id,
        )
    except Exception:
        logger.exception(
            "MAGEN_MEDIA_DB_LINK_FATAL | inspection_id=%s",
            inspection_id,
        )
        raise

    # -------------------------------------------------
    # Resolve client_id (MANDATORY for event log)
    # -------------------------------------------------
    client_row = db.execute(
        text(
            """
            SELECT client_id
            FROM whatsapp_numbers
            WHERE destination_number = :business
              AND status = 'active'
            LIMIT 1
            """
        ),
        {"business": business_msisdn},
    ).mappings().first()

    if not client_row:
        logger.error(
            "MAGEN_EVENT_LOG_CLIENT_FAIL | inspection_id=%s",
            inspection_id,
        )
        return

    # -------------------------------------------------
    # Log event correctly
    # -------------------------------------------------
    try:
        log_event(
            db=db,
            client_id=UUID(str(client_row["client_id"])),
            event_type="MAGEN_INSPECTION_PHOTO_STORED",
            event_detail=(
                f"inspection_id={inspection_id} | "
                f"s3_key={s3_key} | "
                f"media_id={media_id}"
            ),
        )

        logger.info(
            "MAGEN_EVENT_LOG_OK | inspection_id=%s",
            inspection_id,
        )
    except Exception:
        logger.exception(
            "MAGEN_EVENT_LOG_FAIL | inspection_id=%s",
            inspection_id,
        )
