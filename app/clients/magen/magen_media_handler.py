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
- Business identity must be provided by caller (inbound layer)
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


def handle_magen_inspection_media(
    *,
    db: Session,
    sender: str,
    business_msisdn: str,
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
    - Link S3 key to inspection event
    - Fail hard on integrity breach
    """

    if not business_msisdn:
        logger.error(
            "MAGEN_MEDIA_NO_BUSINESS_MSISDN | sender=%s | inspection_id=%s",
            sender,
            inspection_id,
        )
        raise RuntimeError("Business MSISDN required for media handling")

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
    # Download image bytes from Meta (fail hard)
    # -------------------------------------------------
    try:
        image_bytes = meta.download_media(media_id)

        if not image_bytes:
            logger.error(
                "MAGEN_MEDIA_DOWNLOAD_EMPTY | inspection_id=%s | media_id=%s",
                inspection_id,
                media_id,
            )
            raise RuntimeError("Meta download returned empty bytes")

        logger.info(
            "MAGEN_MEDIA_DOWNLOAD_OK | inspection_id=%s | media_id=%s | bytes=%s",
            inspection_id,
            media_id,
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
    # Upload to S3 (fail hard)
    # -------------------------------------------------
    try:
        _s3_store.put_bytes(
            key=s3_key,
            data=image_bytes,
            content_type=mime_type or "image/jpeg",
        )

        logger.info(
            "MAGEN_MEDIA_UPLOAD_OK | inspection_id=%s | media_id=%s | s3_key=%s",
            inspection_id,
            media_id,
            s3_key,
        )

    except Exception:
        logger.exception(
            "MAGEN_MEDIA_UPLOAD_FAIL | inspection_id=%s | media_id=%s | s3_key=%s",
            inspection_id,
            media_id,
            s3_key,
        )
        raise

    # -------------------------------------------------
    # Persist S3 key into magen_inspection_events
    # -------------------------------------------------
    try:
        result = db.execute(
            text(
                """
                UPDATE magen_inspection_events
                SET s3_url = :s3_key
                WHERE inspection_id = :inspection_id
                  AND event_type = 'PHOTO'
                  AND meta_media_id = :meta_media_id
                  AND s3_url IS NULL
                """
            ),
            {
                "s3_key": s3_key,
                "inspection_id": inspection_id,
                "meta_media_id": media_id,
            },
        )

        if result.rowcount != 1:
            db.rollback()

            logger.error(
                "MAGEN_MEDIA_DB_LINK_FAIL | inspection_id=%s | media_id=%s | rowcount=%s",
                inspection_id,
                media_id,
                result.rowcount,
            )

            raise RuntimeError(
                f"PHOTO event linkage failed (rowcount={result.rowcount})"
            )

        db.commit()

        logger.info(
            "MAGEN_MEDIA_DB_LINK_OK | inspection_id=%s | media_id=%s",
            inspection_id,
            media_id,
        )

    except Exception:
        logger.exception(
            "MAGEN_MEDIA_DB_LINK_FATAL | inspection_id=%s | media_id=%s",
            inspection_id,
            media_id,
        )
        raise

        # -------------------------------------------------
    # Log event / metadata (non-UX)
    # -------------------------------------------------
    try:
        log_event(
            db=db,
            event_type="MAGEN_INSPECTION_PHOTO_STORED",
            metadata={
                "inspection_id": inspection_id,
                "site_id": site_id,
                "s3_key": s3_key,
                "content_type": mime_type,
                "sender": sender,
            },
        )
        logger.info(
            "MAGEN_EVENT_LOGGED | inspection_id=%s",
            inspection_id,
        )
    except Exception:
        logger.exception(
            "MAGEN_EVENT_LOG_FAIL | inspection_id=%s",
            inspection_id,
        )
