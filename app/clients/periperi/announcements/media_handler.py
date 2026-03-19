from __future__ import annotations

"""
File: app/client/periperi/announcements/media_handler.py
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
from app.messaging.template_registry import FG_CAMPAIGN_TEMPLATE

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

    if not client_uuid:
        logger.error("ANNOUNCEMENTS_CLIENT_ID_INVALID | raw=%r", client_id)
        return True

    meta = get_meta_client(
        db=db,
        business_msisdn=business_msisdn,
    )

    media_id = msg["image"]["id"]
    caption = msg["image"].get("caption") or DEFAULT_CAPTION

    logger.info(
        "ANNOUNCEMENTS_MEDIA_IMAGE | sender=%s | media_id=%s | caption=%r",
        sender,
        media_id,
        caption,
    )

    try:
        db.execute(
            text(
                """
                INSERT INTO announcements (
                    client_id,
                    media_id,
                    caption,
                    created_at
                )
                VALUES (
                    :client_id,
                    :media_id,
                    :caption,
                    now()
                )
                """
            ),
            {
                "client_id": client_uuid,
                "media_id": media_id,
                "caption": caption,
            },
        )
        db.commit()

        logger.info(
            "ANNOUNCEMENTS_DB_INSERT_OK | client_uuid=%s | media_id=%s",
            client_uuid,
            media_id,
        )

    except Exception as exc:
        db.rollback()
        logger.error(
            "ANNOUNCEMENTS_DB_INSERT_FAIL | client_uuid=%s | media_id=%s | err=%s",
            client_uuid,
            media_id,
            exc,
            exc_info=True,
        )
        return True

    # UUID-only admin fetch
    try:
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
            ).all()
        }
    except Exception:
        logger.exception("ANNOUNCEMENTS_ADMIN_FETCH_FAIL")
        return True

    try:
        contacts = (
            db.query(Contact)
            .filter(~Contact.contact_number.in_(admin_numbers))
            .all()
        )

        logger.info(
            "ANNOUNCEMENTS_PUSH_BEGIN | recipients=%s",
            len(contacts),
        )

    except Exception as exc:
        logger.error(
            "ANNOUNCEMENTS_CONTACT_FETCH_FAIL | err=%s",
            exc,
            exc_info=True,
        )
        return True

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
        except Exception as exc:
            failed += 1
            logger.error(
                "ANNOUNCEMENTS_SEND_FAIL | to=%s | err=%s",
                c.contact_number,
                exc,
                exc_info=True,
            )

    logger.info(
        "ANNOUNCEMENTS_PUSH_DONE | sent=%s | failed=%s",
        sent,
        failed,
    )

    try:
        meta.send_template(
            to_msisdn=sender,
            template_name=FG_CAMPAIGN_TEMPLATE,
            body_params=[
                f"Announcement sent to customers. Delivered: {sent}. Failed: {failed}."
            ],
        )
        logger.info("ANNOUNCEMENTS_ADMIN_CONFIRM_OK | sender=%s", sender)

    except Exception as exc:
        logger.error(
            "ANNOUNCEMENTS_ADMIN_CONFIRM_FAIL | sender=%s | err=%s",
            sender,
            exc,
            exc_info=True,
        )

    return True
