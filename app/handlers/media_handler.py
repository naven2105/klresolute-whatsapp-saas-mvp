from __future__ import annotations

"""
File: app/handlers/media_handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Handle admin image messages for SPECIALS.

RULE (LOCKED):
- Admin sends image + caption → SPECIAL
- Stored in specials table (latest wins)
- Immediately pushed to all customers
- Can be replayed later via "SPECIALS"
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models import Contact
from app.outbound.factory import get_meta_client
from app.utils.admin import is_admin_message

# -------------------------------------------------
# Logging
# -------------------------------------------------

logger = logging.getLogger("media_handler")

DEFAULT_CAPTION = "Today’s specials"


def _resolve_client_uuid(db: Session, *, client_id_int: int) -> str | None:
    """
    Resolve UUID client_id from integer klresolute_client_id.
    """
    try:
        row = (
            db.execute(
                text(
                    """
                    SELECT client_id
                    FROM whatsapp_numbers
                    WHERE klresolute_client_id = :cid
                      AND status = 'active'
                    LIMIT 1
                    """
                ),
                {"cid": client_id_int},
            )
            .mappings()
            .first()
        )

        if not row:
            logger.error(
                "MEDIA_CLIENT_UUID_NOT_FOUND | client_id_int=%s",
                client_id_int,
            )
            return None

        return str(row["client_id"])

    except Exception as exc:
        logger.exception(
            "MEDIA_CLIENT_UUID_RESOLUTION_FAIL | client_id_int=%s | err=%s",
            client_id_int,
            exc,
        )
        return None


def handle_media_message(
    *,
    db: Session,
    sender: str,
    msg: dict,
    client_id,
    business_msisdn: str,
) -> bool:
    """
    Returns True if message was handled.
    Returns False if message is NOT an image.
    """

    logger.info(
        "MEDIA_HANDLER_ENTER | sender=%s | msg_type=%s | client_id=%s",
        sender,
        msg.get("type"),
        client_id,
    )

    # -------------------------------------------------
    # Only images handled here
    # -------------------------------------------------
    if msg.get("type") != "image":
        logger.debug("MEDIA_HANDLER_SKIP | not image")
        return False

    # -------------------------------------------------
    # Admin-only rule (DB-driven)
    # -------------------------------------------------
    if not is_admin_message(
        db=db,
        sender=sender,
        business_msisdn=business_msisdn,
    ):
        logger.warning(
            "MEDIA_HANDLER_REJECT | non-admin sender=%s",
            sender,
        )
        return True  # consumed but ignored

    # -------------------------------------------------
    # Guard + resolve UUID client_id
    # -------------------------------------------------
    try:
        client_id_int = int(str(client_id))
    except Exception:
        logger.error(
            "MEDIA_CLIENT_ID_INVALID | client_id=%r",
            client_id,
        )
        return True

    client_uuid = _resolve_client_uuid(
        db,
        client_id_int=client_id_int,
    )

    if not client_uuid:
        return True

    meta = get_meta_client()

    media_id = msg["image"]["id"]
    caption = msg["image"].get("caption") or DEFAULT_CAPTION

    logger.info(
        "MEDIA_HANDLER_IMAGE | sender=%s | media_id=%s | caption=%r",
        sender,
        media_id,
        caption,
    )

    # -------------------------------------------------
    # Store SPECIAL (latest wins) — UUID SAFE
    # -------------------------------------------------
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
            "MEDIA_HANDLER_DB_OK | client_uuid=%s | media_id=%s",
            client_uuid,
            media_id,
        )

    except Exception as exc:
        logger.error(
            "MEDIA_HANDLER_DB_FAIL | client_uuid=%s | media_id=%s | error=%s",
            client_uuid,
            media_id,
            exc,
            exc_info=True,
        )
        return True

    # -------------------------------------------------
    # Resolve admins (exclude from recipients)
    # -------------------------------------------------
    admin_numbers = {
        row[0]
        for row in db.execute(
            text(
                """
                SELECT msisdn
                FROM client_admins
                WHERE client_code = :client
                  AND is_active = TRUE
                """
            ),
            {"client": business_msisdn},
        ).all()
    }

    # -------------------------------------------------
    # Push SPECIAL to all customers
    # -------------------------------------------------
    try:
        contacts = (
            db.query(Contact)
            .filter(~Contact.contact_number.in_(admin_numbers))
            .all()
        )

        logger.info(
            "MEDIA_HANDLER_BROADCAST_BEGIN | recipients=%s",
            len(contacts),
        )

    except Exception as exc:
        logger.error(
            "MEDIA_HANDLER_CONTACT_FETCH_FAIL | error=%s",
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
                "MEDIA_HANDLER_SEND_FAIL | to=%s | error=%s",
                c.contact_number,
                exc,
                exc_info=True,
            )

    logger.info(
        "MEDIA_HANDLER_BROADCAST_DONE | sent=%s | failed=%s",
        sent,
        failed,
    )

    # -------------------------------------------------
    # Confirm to admin
    # -------------------------------------------------
    try:
        meta.send_generic_business_update_template(
            to_msisdn=sender,
            blob_text=(
                f"Special sent to customers. "
                f"Delivered: {sent}. Failed: {failed}."
            ),
        )
        logger.info(
            "MEDIA_HANDLER_ADMIN_CONFIRM_OK | sender=%s",
            sender,
        )

    except Exception as exc:
        logger.error(
            "MEDIA_HANDLER_ADMIN_CONFIRM_FAIL | sender=%s | error=%s",
            sender,
            exc,
            exc_info=True,
        )

    return True
