from __future__ import annotations

"""
File: app/clients/magen/inspection_events_repo.py
Path: app/clients/magen/inspection_events_repo.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Persist inspection events for Magen Security.

Responsibilities (LOCKED):
- Insert inspection events
- Update inspection last_event_at timestamp

Notes:
- Pure DB writes
- No messaging
- No inspection lifecycle logic
"""

from sqlalchemy.orm import Session
from sqlalchemy import text


def insert_event(
    db: Session,
    *,
    inspection_id: int,
    event_type: str,
    meta_media_id: str | None = None,
    gps_lat: float | None = None,
    gps_lng: float | None = None,
    caption: str | None = None,
):
    db.execute(
        text(
            """
            INSERT INTO magen_inspection_events (
                inspection_id,
                event_type,
                meta_media_id,
                gps_lat,
                gps_lng,
                caption
            )
            VALUES (
                :inspection_id,
                :event_type,
                :meta_media_id,
                :gps_lat,
                :gps_lng,
                :caption
            );

            UPDATE magen_inspections
            SET last_event_at = now()
            WHERE inspection_id = :inspection_id;
            """
        ),
        {
            "inspection_id": inspection_id,
            "event_type": event_type,
            "meta_media_id": meta_media_id,
            "gps_lat": gps_lat,
            "gps_lng": gps_lng,
            "caption": caption,
        },
    )
    db.commit()
