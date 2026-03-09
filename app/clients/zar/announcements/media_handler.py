from __future__ import annotations

"""
File: media_handler.py
Path: app/clients/zar/announcements/media_handler.py
Project: KLResolute WhatsApp SaaS MVP

Sprint: Full UUID Identity Migration

Changes:
- UUID-only identity model
- Defensive rollback protection retained
- No behaviour changes
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models import Contact
from app.outbound.factory import get_meta_client
from app.utils.admin import is_admin_message
from app.messaging.template_registry import ZAR_CAMPAIGN_TEMPLATE

logger = logging.getLogger("announcements.admin_media")

DEFAULT_CAPTION = "Latest announcement"


def handle_media_message(
    *,
    db: Session,
    sender: str,
    msg: dict,
    client_id,
    business_msisdn: str,
) -> bool:

    logger.info(
        "ANNOUNCEMENTS_MEDIA_ENTER | sender=%s | msg_type=%s | client_id=%s",
        sender,
        msg.get("type"),
        client_id,
    )

    try:
        db.rollback()
    except Exception:
        logger.exception("ANNOUNCEMENTS_DB_RESET_FAIL | sender=%s", sender)

    if msg.get("type") != "image":
        logger.debug("ANNOUNCEMENTS_MEDIA_SKIP | reason=not_image")
        return False

    if not is_admin_message(
        db=db,
        sender=sender,
        business_msisdn=business_msisdn,
    ):
        logger.warning(
            "ANNOUNCEMENTS_MEDIA_REJECT | reason=non_admin | sender=%s",
            sender,
        )
        return True

    client_uuid = str(client_id)

    meta = get_meta_client(
        db=db,
        business_msisdn=business_msisdn,
    )

    media_id = msg["image"]["id"]
    caption = msg["image"].get("caption") or DEFAULT_CAPTION

    db.execute(
        text(
            """
            INSERT INTO announcements
            (client_id, media_id, caption, created_at)
            VALUES (:client_id, :media_id, :caption, now())
            """
        ),
        {
            "client_id": client_uuid,
            "media_id": media_id,
            "caption": caption,
        },
    )

    db.commit()

    admin_numbers = {
        row[0]
        for row in db.execute(
            text(
                """
                SELECT msisdn
                FROM client_admins
                WHERE client_id = :client_id
                AND is_active = TRUE
                """
            ),
            {"client_id": client_uuid},
        )
    }

    contacts = (
        db.query(Contact)
        .filter(~Contact.contact_number.in_(admin_numbers))
        .all()
    )

    sent = 0
    failed = 0

    for c in contacts:

        try:

            meta.send_image_message(
                to_msisdn=c.contact_number,
                media_id=media_id,
                caption=caption,
            )

            sent += 1

        except Exception:

            failed += 1
            logger.exception("ANNOUNCEMENTS_SEND_FAIL")

    meta.send_template(
        to_msisdn=sender,
        template_name=ZAR_CAMPAIGN_TEMPLATE,
        body_params=[
            f"Announcement sent to customers. Delivered: {sent}. Failed: {failed}."
        ],
    )

    return True