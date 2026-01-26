from __future__ import annotations

"""
File: app/clients/magen/inbound.py
Path: app/clients/magen/inbound.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Inbound router for Magen Security inspections.

Responsibilities (LOCKED):
- Validate Magen business number
- Validate staff sender
- Auto-start inspection on first PHOTO or GPS
- Capture PHOTO / GPS / NOTE events
- Update last_event_at on every event
- Log all failures explicitly (NO silent errors)
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.messaging.client_messenger import send_message

logger = logging.getLogger("clients.magen")

MAGEN_BUSINESS_MSISDN = "27631016099"


# -------------------------------------------------
# Helpers
# -------------------------------------------------

def _get_active_inspection(db: Session, sender: str):
    try:
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
    except Exception:
        logger.exception("MAGEN_FETCH_ACTIVE_INSPECTION_FAIL | sender=%s", sender)
        return None


def _start_inspection(db: Session, sender: str):
    try:
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

        logger.info(
            "MAGEN_INSPECTION_STARTED | sender=%s | inspection_id=%s",
            sender,
            row.inspection_id,
        )
        return row.inspection_id

    except Exception:
        db.rollback()
        logger.exception("MAGEN_START_INSPECTION_FAIL | sender=%s", sender)
        raise


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
    try:
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

        logger.info(
            "MAGEN_EVENT_CAPTURED | inspection_id=%s | sender=%s | type=%s",
            inspection_id,
            sender,
            event_type,
        )

    except Exception:
        db.rollback()
        logger.exception(
            "MAGEN_EVENT_INSERT_FAIL | inspection_id=%s | sender=%s | type=%s",
            inspection_id,
            sender,
            event_type,
        )
        raise


# -------------------------------------------------
# Inbound handler
# -------------------------------------------------

def handle_inbound(
    *,
    db: Session,
    msg: dict,
    sender: str,
    business_msisdn: str,
) -> bool:

    if business_msisdn != MAGEN_BUSINESS_MSISDN:
        return False

    # ----------------------------------
    # Staff validation
    # ----------------------------------
    try:
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
    except Exception:
        logger.exception("MAGEN_STAFF_LOOKUP_FAIL | sender=%s", sender)
        return True

    if not staff:
        send_message(
            to_number=sender,
            text=(
                "Magen Security WhatsApp\n"
                "Internal inspections only."
            ),
        )
        logger.warning("MAGEN_PUBLIC_MESSAGE_BLOCKED | sender=%s", sender)
        return True

    msg_type = msg.get("type")
    active = _get_active_inspection(db, sender)

    # -------------------------------
    # IMAGE
    # -------------------------------
    if msg_type == "image":
        inspection_id = (
            active.inspection_id if active else _start_inspection(db, sender)
        )

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
        inspection_id = (
            active.inspection_id if active else _start_inspection(db, sender)
        )

        loc = msg["location"]

        _insert_event(
            db,
            inspection_id=inspection_id,
            sender=sender,
            event_type="GPS",
            lat=loc.get("latitude"),
            lng=loc.get("longitude"),
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
            logger.info(
                "MAGEN_TEXT_WITHOUT_ACTIVE_INSPECTION | sender=%s",
                sender,
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

    logger.warning(
        "MAGEN_UNSUPPORTED_MESSAGE_TYPE | sender=%s | type=%s",
        sender,
        msg_type,
    )
    return True
