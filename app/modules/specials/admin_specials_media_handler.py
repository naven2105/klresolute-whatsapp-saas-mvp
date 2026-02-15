from __future__ import annotations

"""
File: app/modules/specials/admin_specials_media_handler.py
Project: KLResolute WhatsApp SaaS MVP

Sprint: Full UUID Identity Migration

Changes:
- Removed klresolute_client_id usage
- UUID-only identity model
- Removed integer resolution helper
- Added defensive rollback protection
- FIX: client_admins lookup now uses client_code (UUID)
- No behaviour changes
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models import Contact
from app.outbound.factory import get_meta_client
from app.utils.admin import is_admin_message

logger = logging.getLogger("specials.admin_media")

DEFAULT_CAPTION = "Today’s specials"


def handle_media_message(
    *,
    db: Session,
    sender: str,
    msg: dict,
    client_id,
    business_msisdn: str,
) -> bool:

    logger.info(
        "SPECIALS_MEDIA_ENTER | sender=%s | msg_type=%s | client_id=%s",
        sender,
        msg.get("type"),
        client_id,
    )

    try:
        db.rollback()
    except Exception:
        logger.exception("SPECIALS_DB_RESET_FAIL | sender=%s", sender)

    if msg.get("type") != "image":
        logger.debug("SPECIALS_MEDIA_SKIP | reason=not_image")
        return False

    if not is_admin_message(
        db=db,
        sender=sender,
        business_msisdn=business_msisdn,
    ):
        logger.warning(
            "SPECIALS_MEDIA_REJECT | reason=non_admin | sender=%s",
            sender,
        )
        return True

    client_uuid = str(client_id)

    if not client_uuid:
        logger.error("SPECIALS_CLIENT_ID_INVALID | raw=%r", client_id)
        return True

    meta = get_meta_client(
        db=db,
        business_msisdn=business_msisdn,
    )

    media_id = msg["image"]["id"]
    caption = msg["image"].get("caption") or DEFAULT_CAPTION

    logger.info(
        "SPECIALS_MEDIA_IMAGE | sender=%s | media_id=%s | caption=%r",
        sender,
        media_id,
        caption,
    )

    try:
        db.execute(
            text(
                """
                INSERT INTO specials (
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
            "SPECIALS_DB_INSERT_OK | client_uuid=%s | media_id=%s",
            client_uuid,
            media_id,
        )

    except Exception as exc:
        db.rollback()
        logger.error(
            "SPECIALS_DB_INSERT_FAIL | client_uuid=%s | media_id=%s | err=%s",
            client_uuid,
            media_id,
            exc,
            exc_info=True,
        )
        return True

    # ✅ FIXED HERE
    try:
        admin_numbers = {
            row[0]
            for row in db.execute(
                text(
                    """
                    SELECT msisdn
                    FROM client_admins
                    WHERE client_code = :client_code
                      AND is_active = TRUE
                    """
                ),
                {"client_code": client_uuid},
            ).all()
        }
    except Exception:
        logger.exception("SPECIALS_ADMIN_FETCH_FAIL")
        return True

    try:
        contacts = (
            db.query(Contact)
            .filter(~Contact.contact_number.in_(admin_numbers))
            .all()
        )

        logger.info(
            "SPECIALS_PUSH_BEGIN | recipients=%s",
            len(contacts),
        )

    except Exception as exc:
        logger.error(
            "SPECIALS_CONTACT_FETCH_FAIL | err=%s",
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
                "SPECIALS_SEND_FAIL | to=%s | err=%s",
                c.contact_number,
                exc,
                exc_info=True,
            )

    logger.info(
        "SPECIALS_PUSH_DONE | sent=%s | failed=%s",
        sent,
        failed,
    )

    try:
        meta.send_generic_business_update_template(
            to_msisdn=sender,
            blob_text=(
                f"Special sent to customers. "
                f"Delivered: {sent}. Failed: {failed}."
            ),
        )
        logger.info("SPECIALS_ADMIN_CONFIRM_OK | sender=%s", sender)

    except Exception as exc:
        logger.error(
            "SPECIALS_ADMIN_CONFIRM_FAIL | sender=%s | err=%s",
            sender,
            exc,
            exc_info=True,
        )

    return True
