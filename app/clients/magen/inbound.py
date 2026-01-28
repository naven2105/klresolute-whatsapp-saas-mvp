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

from app.messaging.client_messenger import send_message
from app.clients.magen.workers.pdf_worker import generate_and_send_inspection_pdf

from app.clients.magen.inspection_service import (
    get_active_inspection,
    start_inspection,
    close_inspection,
)
from app.clients.magen.inspection_events_repo import insert_event
from app.clients.magen.staff_repo import is_active_staff

logger = logging.getLogger("clients.magen")

MAGEN_BUSINESS_MSISDN = "27631016099"


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
                    to_number=sender,
                    text="No active inspection to close.",
                )
                return True

            inspection_id = active.inspection_id

            # --- Guaranteed ACK via template (Magen only) ---
            send_message(
                to_number=sender,
                template_name="magen_inspection_completed",
                language_code="en_US",
            )

            # --- Close inspection ---
            close_inspection(
                db,
                inspection_id=inspection_id,
                status="DONE",
            )

            # --- Post-close processing ---
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
        inspection_id = (
            active.inspection_id
            if active
            else start_inspection(db, sender=sender)
        )

        media_id = msg["image"]["id"]
        caption = msg["image"].get("caption")

        insert_event(
            db,
            inspection_id=inspection_id,
            event_type="PHOTO",
            meta_media_id=media_id,
            caption=caption,
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
    # TEXT NOTE
    # ----------------------------------
    if msg_type == "text":
        if not active:
            send_message(
                to_number=sender,
                text="Send a photo or location to start an inspection.",
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
