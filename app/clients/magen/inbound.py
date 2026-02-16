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
- Media evidence must be stored in S3 and linked to events (fail hard)
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.messaging.client_messenger import send_message

from app.clients.magen.inspection.pdf_worker import (
    generate_and_send_inspection_pdf,
)

from app.clients.magen.inspection.service import (
    get_active_inspection,
    start_inspection,
    close_inspection,
)

from app.clients.magen.inspection.events_repo import (
    insert_event,
)

from app.clients.magen.staff_repo import is_active_staff

from app.clients.magen.magen_media_handler import (
    handle_magen_inspection_media,
)

logger = logging.getLogger("clients.magen")

MAGEN_BUSINESS_MSISDN = "27631016099"


def _next_photo_index(db: Session, *, inspection_id: str) -> int:
    """
    Compute next photo index for deterministic S3 naming.

    Guard rails:
    - Deterministic ordering
    - No reliance on client-provided indices
    """
    row = (
        db.execute(
            text(
                """
                SELECT COUNT(*) AS cnt
                FROM magen_inspection_events
                WHERE inspection_id = :id
                  AND event_type = 'PHOTO'
                """
            ),
            {"id": inspection_id},
        )
        .mappings()
        .first()
    )

    count = int(row["cnt"]) if row and row["cnt"] is not None else 0
    return count + 1


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

    # ----------------------------------
    # Ensure this is the Magen bot
    # ----------------------------------
    if business_msisdn != MAGEN_BUSINESS_MSISDN:
        return False

    # ----------------------------------
    # Validate staff
    # ----------------------------------
    if not is_active_staff(db, msisdn=sender):
        send_message(
            db=db,
            business_msisdn=business_msisdn,
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
    active = get_active_inspection(db, sender=sender)

    # ----------------------------------
    # DONE command (manual close)
    # ----------------------------------
    if msg_type == "text":
        text_body = msg["text"]["body"].strip().lower()

        if text_body == "done":
            if not active:
                send_message(
                    db=db,
                    business_msisdn=business_msisdn,
                    to_number=sender,
                    text="No active inspection to close.",
                )
                return True

            inspection_id = active.inspection_id

            # --- Guaranteed ACK via template (Magen only) ---
            send_message(
                db=db,
                business_msisdn=business_msisdn,
                to_number=sender,
                template_name="magen_inspection_completed",
                language_code="en_US",
            )

            # --- Close inspection (NEW lifecycle model: ACTIVE/CLOSED + reason) ---
            close_inspection(
                db,
                inspection_id=inspection_id,
                status="CLOSED",
                closed_reason="MANUAL",
            )

            # --- Post-close processing ---
            generate_and_send_inspection_pdf(
                db=db,
                inspection_id=inspection_id,
            )

            logger.info(
                "MAGEN_INSPECTION_CLOSED_MANUAL | sender=%s | id=%s",
                sender,
                inspection_id,
            )
            return True

    # ----------------------------------
    # IMAGE
    # ----------------------------------
    if msg_type == "image":
        inspection_id = (
            active.inspection_id
            if active
            else start_inspection(db, sender=sender)
        )

        media_id = msg["image"]["id"]
        caption = msg["image"].get("caption")

        # Determine deterministic photo index BEFORE insert
        photo_index = _next_photo_index(db, inspection_id=inspection_id)

        # Insert PHOTO event first (links via meta_media_id + inspection_id)
        insert_event(
            db,
            inspection_id=inspection_id,
            event_type="PHOTO",
            meta_media_id=media_id,
            caption=caption,
        )

        # Store media in S3 + link s3_url back onto PHOTO row (FAIL HARD)
        # site_id not yet captured in workflow -> keep deterministic placeholder for now
        handle_magen_inspection_media(
            db=db,
            sender=sender,
            business_msisdn=business_msisdn,
            media_id=media_id,
            mime_type="image/jpeg",
            inspection_id=str(inspection_id),
            site_id="UNSPECIFIED",
            photo_index=photo_index,
        )

        return True

    # ----------------------------------
    # LOCATION
    # ----------------------------------
    if msg_type == "location":
        inspection_id = (
            active.inspection_id
            if active
            else start_inspection(db, sender=sender)
        )

        loc = msg["location"]

        insert_event(
            db,
            inspection_id=inspection_id,
            event_type="GPS",
            gps_lat=loc["latitude"],
            gps_lng=loc["longitude"],
        )
        return True

    # ----------------------------------
    # TEXT NOTE / STAFF MENU
    # ----------------------------------
    if msg_type == "text":
        if not active:
            send_message(
                db=db,
                business_msisdn=business_msisdn,
                to_number=sender,
                text=(
                    "Magen Inspection Bot\n\n"
                    "• Send a photo to start a new inspection.\n"
                    "• Send location if required.\n"
                    "• Send notes anytime during an active inspection.\n"
                    "• Send DONE to close the inspection.\n\n"
                    "Inspections auto-close after 5 minutes of inactivity."
                ),
            )
            return True

        insert_event(
            db,
            inspection_id=active.inspection_id,
            event_type="NOTE",
            caption=msg["text"]["body"].strip(),
        )
        return True

    return True
