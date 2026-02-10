from __future__ import annotations

"""
File: app/modules/specials/admin_specials_media_handler.py
Project: KLResolute WhatsApp SaaS MVP

ROLE (EXPLICIT & LOCKED):
Admin → SPECIALS creation handler.

This handler processes ADMIN IMAGE messages and interprets them
as SPECIALS for clients whose customer menu exposes the SPECIALS feature.

BUSINESS MEANING:
- Admin sends image (+ optional caption)
- Image is stored as the latest SPECIAL (latest wins)
- SPECIAL is immediately pushed to customers
- SPECIAL can later be replayed via customer menu

GUARD RAILS (MANDATORY):
- MUST NEVER raise exceptions
- MUST NEVER break or interrupt caller flow
- MUST return True once image is consumed
- MUST fail safely and log clearly (Render-friendly)

NON-GOALS:
- Not a generic media handler
- Not customer-facing
- Not a broadcast system
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

logger = logging.getLogger("specials.admin_media")

DEFAULT_CAPTION = "Today’s specials"


def _resolve_client_uuid(db: Session, *, client_id_int: int) -> str | None:
    """
    Resolve UUID client_id from integer klresolute_client_id.

    Guarded:
    - Returns None on any failure
    - Never raises
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
                "SPECIALS_CLIENT_UUID_NOT_FOUND | client_id_int=%s",
                client_id_int,
            )
            return None

        return str(row["client_id"])

    except Exception as exc:
        logger.exception(
            "SPECIALS_CLIENT_UUID_RESOLUTION_FAIL | client_id_int=%s | err=%s",
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
    Admin image entry point for SPECIALS.

    Returns:
    - False → not an image (caller may continue routing)
    - True  → image consumed (success or safe failure)
    """

    logger.info(
        "SPECIALS_MEDIA_ENTER | sender=%s | msg_type=%s | client_id=%s",
        sender,
        msg.get("type"),
        client_id,
    )

    # -------------------------------------------------
    # Only images handled here
    # -------------------------------------------------
    if msg.get("type") != "image":
        logger.debug("SPECIALS_MEDIA_SKIP | reason=not_image")
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
            "SPECIALS_MEDIA_REJECT | reason=non_admin | sender=%s",
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
            "SPECIALS_CLIENT_ID_INVALID | raw_client_id=%r",
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
        "SPECIALS_MEDIA_IMAGE | sender=%s | media_id=%s | caption=%r",
        sender,
        media_id,
        caption,
    )

    # -------------------------------------------------
    # Store SPECIAL (latest wins)
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
            "SPECIALS_DB_INSERT_OK | client_uuid=%s | media_id=%s",
            client_uuid,
            media_id,
        )

    except Exception as exc:
        logger.error(
            "SPECIALS_DB_INSERT_FAIL | client_uuid=%s | media_id=%s | err=%s",
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
            "SPECIALS_ADMIN_CONFIRM_OK | sender=%s",
            sender,
        )

    except Exception as exc:
        logger.error(
            "SPECIALS_ADMIN_CONFIRM_FAIL | sender=%s | err=%s",
            sender,
            exc,
            exc_info=True,
        )

    return True
