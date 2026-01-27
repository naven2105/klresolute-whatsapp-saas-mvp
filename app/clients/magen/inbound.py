from __future__ import annotations

"""
File: app/clients/magen/inbound.py
Path: app/clients/magen/inbound.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Inbound router for Magen Security inspections.

Rules (LOCKED):
- Inspection starts on first PHOTO or GPS
- Officers may send notes anytime during ACTIVE inspection
- 'done' immediately closes inspection
- PDF worker is triggered on close
- No menus, no delegation
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.messaging.client_messenger import send_message
from app.clients.magen.workers.pdf_worker import generate_and_send_inspection_pdf

from app.clients.magen.magen_media_handler import handle_magen_inspection_media

logger = logging.getLogger("clients.magen")

MAGEN_BUSINESS_MSISDN = "27631016099"


# -------------------------------------------------
# Helpers
# -------------------------------------------------

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


def _start_inspection(db: Session, sender: str) -> int:
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

    inspection_id = row.inspection_id
    logger.info("MAGEN_INSPECTION_STARTED | sender=%s | id=%s", sender, inspection_id)
    return inspection_id


def _close_inspection(db: Session, inspection_id: int, status: str):
    db.execute(
        text(
            """
            UPDATE magen_inspections
            SET status = :status,
                completed_at = now()
            WHERE inspection_id = :id
            """
        ),
        {"id": inspection_id, "status": status},
    )
    db.commit()


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
    """
    Insert a single inspection event.
    Schema-aligned with magen_inspection_events.
    """

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
            "meta_media_id": media_id,
            "gps_lat": lat,
            "gps_lng": lng,
            "caption": caption,
        },
    )
    db.commit()



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
    # Validate staff
    # ----------------------------------
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
                "Internal inspections only.\n"
                "Please visit www.KLResolute.co.za"
            ),
        )
        logger.info("MAGEN_PUBLIC_BLOCK | sender=%s", sender)
        return True

    msg_type = msg.get("type")
    active = _get_active_inspection(db, sender)

    # ----------------------------------
    # DONE command (manual close)
    # ----------------------------------
    if msg_type == "text":
        text_body = msg["text"]["body"].strip().lower()

        if text_body == "done":
            if not active:
                send_message(
                    to_number=sender,
                    text="No active inspection to close.",
                )
                return True

            inspection_id = active.inspection_id

            # --- GUARANTEED officer confirmation (send FIRST) ---
            send_message(
                to_number=sender,
                text="✅ Inspection completed. Thank you.",
            )

            # --- Now close inspection ---
            _close_inspection(db, inspection_id, status="DONE")

            # --- Post-close processing (non-interactive) ---
            generate_and_send_inspection_pdf(
                db=db,
                inspection_id=inspection_id,
            )

            logger.info(
                "MAGEN_INSPECTION_DONE | sender=%s | id=%s",
                sender,
                inspection_id,
            )
            return True

    # ----------------------------------
    # IMAGE
    # ----------------------------------
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

    # ----------------------------------
    # LOCATION
    # ----------------------------------
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

    # ----------------------------------
    # TEXT NOTE
    # ----------------------------------
    if msg_type == "text":
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
            caption=msg["text"]["body"].strip(),
        )
        return True

    return True
