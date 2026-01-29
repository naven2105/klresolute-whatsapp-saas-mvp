from __future__ import annotations

"""
File: app/modules/inspection/handler.py
Path: app/modules/inspection/handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Inspection module inbound handler.
"""

from typing import Dict
from sqlalchemy.orm import Session

from app.modules.inspection.profiles import INSPECTION_PROFILES
from app.modules.inspection.service import (
    get_active_inspection,
    start_inspection,
    close_inspection,
)
from app.modules.inspection.repo import insert_event
from app.messaging.client_messenger import send_message


def handle(
    *,
    db: Session,
    msg: Dict,
    sender: str,
    profile_code: str,
) -> bool:
    profile = INSPECTION_PROFILES[profile_code]
    msg_type = msg.get("type")
    active = get_active_inspection(db, sender=sender)

    # DONE
    if msg_type == "text" and msg["text"]["body"].strip().lower() == "done":
        if not active:
            send_message(
                to_number=sender,
                text="No active inspection to close.",
            )
            return True

        send_message(
            to_number=sender,
            template_name=profile["templates"]["completion"],
            language_code="en_US",
        )

        close_inspection(
            db,
            inspection_id=active.inspection_id,
            status="DONE",
        )
        return True

    # IMAGE
    if msg_type == "image":
        inspection_id = (
            active.inspection_id
            if active
            else start_inspection(db, sender=sender)
        )

        insert_event(
            db,
            inspection_id=inspection_id,
            event_type="PHOTO",
            meta_media_id=msg["image"]["id"],
            caption=msg["image"].get("caption"),
        )
        return True

    # LOCATION
    if msg_type == "location":
        inspection_id = (
            active.inspection_id
            if active
            else start_inspection(db, sender=sender)
        )

        insert_event(
            db,
            inspection_id=inspection_id,
            event_type="GPS",
            gps_lat=msg["location"]["latitude"],
            gps_lng=msg["location"]["longitude"],
        )
        return True

    # NOTE
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

    return False
