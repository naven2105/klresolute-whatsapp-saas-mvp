from __future__ import annotations

"""
File: app/clients/magen/inbound.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Inbound router for Magen Security inspections.
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.messaging.client_messenger import send_message

logger = logging.getLogger("clients.magen")

MAGEN_BUSINESS_MSISDN = "27631016099"


def _get_active_inspection(db: Session, sender: str):
    return db.execute(
        text(
            """
            SELECT inspection_id
            FROM magen_inspections
            WHERE officer_msisdn = :msisdn
              AND status = 'ACTIVE'
            LIMIT 1
            """
        ),
        {"msisdn": sender},
    ).first()


def _start_inspection(db: Session, sender: str):
    row = db.execute(
        text(
            """
            INSERT INTO magen_inspections (officer_msisdn, status)
            VALUES (:msisdn, 'ACTIVE')
            RETURNING inspection_id
            """
        ),
        {"msisdn": sender},
    ).first()
    db.commit()
    return row.inspection_id


def _insert_event(
    db: Session,
    *,
    inspection_id: int,
    sender: str,
    event_type: str,
    media_id: str | None = None,
    lat: float | None = None,
    lng: float | None = None,
    caption: str | None = None,
):
    db.execute(
        text(
            """
            INSERT INTO magen_inspection_events (
                inspection_id,
                officer_msisdn,
                event_type,
                media_id,
                latitude,
                longitude,
                caption
            )
            VALUES (
                :inspection_id,
                :msisdn,
                :event_type,
                :media_id,
                :lat,
                :lng,
                :caption
            );

            UPDATE magen_inspections
            SET last_event_at = now()
            WHERE inspection_id = :inspection_id;
            """
        ),
        {
            "inspection_id": inspection_id,
            "msisdn": sender,
            "event_type": event_type,
            "media_id": media_id,
            "lat": lat,
            "lng": lng,
            "caption": caption,
        },
    )
    db.commit()


def handle_inbound(
    *,
    db: Session,
    msg: dict,
    sender: str,
    business_msisdn: str,
) -> bool:

    if business_msisdn != MAGEN_BUSINESS_MSISDN:
        return False

    staff = db.execute(
        text(
            """
            SELECT 1
            FROM magen_staff
            WHERE msisdn = :msisdn
              AND is_active = TRUE
            LIMIT 1
            """
        ),
        {"msisdn": sender},
    ).first()

    if not staff:
        send_message(
            to_number=sender,
            text=(
                "Magen Security WhatsApp\n"
                "Internal inspections only."
            ),
        )
        return True

    msg_type = msg.get("type")
    active = _get_active_inspection(db, sender)

    # -------------------------------
    # IMAGE
    # -------------------------------
    if msg_type == "image":
        inspection_id = active.inspection_id if active else _start_inspection(db, sender)

        media_id = msg["image"]["id"]
        caption = msg["image"].get("caption")

        _insert_event(
            db,
            inspection_id=inspection_id,
            sender=sender,
            event_type="PHOTO",
            media_id=media_id,
            caption=caption,
        )

        return True

    # -------------------------------
    # LOCATION
    # -------------------------------
    if msg_type == "location":
        inspection_id = active.inspection_id if active else _start_inspection(db, sender)

        loc = msg["location"]

        _insert_event(
            db,
            inspection_id=inspection_id,
            sender=sender,
            event_type="GPS",
            lat=loc["latitude"],
            lng=loc["longitude"],
        )

        return True

    # -------------------------------
    # TEXT NOTE
    # -------------------------------
    if msg_type == "text":
        text_body = msg["text"]["body"].strip()

        if not active:
            send_message(
                to_number=sender,
                text="Send a photo or location to start an inspection.",
            )
            return True

        _insert_event(
            db,
            inspection_id=active.inspection_id,
            sender=sender,
            event_type="NOTE",
            caption=text_body,
        )
        return True

    return True
