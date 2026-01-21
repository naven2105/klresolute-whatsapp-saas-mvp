from __future__ import annotations

"""
File: app/handlers/admin_messaging.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Admin outbound messaging commands.

Handles:
- SEND
- BROADCAST
- PAUSE / RESUME

Rules:
- Admin-only
- Always reply to admin
- Admin replies use TEMPLATE messages only
"""

import logging
from sqlalchemy.orm import Session

from app.models import Contact
from app.outbound.factory import get_meta_client
from app.survey.survey_constants import ADMIN_SURVEY_ALREADY_ACTIVE_TEMPLATE

logger = logging.getLogger("admin_messaging")


def handle_admin_messaging(
    *,
    db: Session,
    sender_number: str,
    text_clean: str,
    upper: str,
    admin_allowlist: set[str],
) -> bool:
    """
    Returns True if handled, False if not recognised.
    """

    if sender_number not in admin_allowlist:
        logger.info("ADMIN_MSG_REJECT | sender=%s", sender_number)
        return False

    meta = get_meta_client()
    paused = getattr(meta, "is_paused", False)

    logger.info(
        "ADMIN_MSG_ENTER | sender=%s | paused=%s | text=%r",
        sender_number,
        paused,
        text_clean,
    )

    # -------------------------------------------------
    # PAUSE
    # -------------------------------------------------
    if upper == "PAUSE":
        meta.is_paused = True
        db.commit()

        logger.info("ADMIN_MSG_PAUSED")

        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text="⏸️ Outbound messaging is now PAUSED.",
        )
        return True

    # -------------------------------------------------
    # RESUME
    # -------------------------------------------------
    if upper == "RESUME":
        meta.is_paused = False
        db.commit()

        logger.info("ADMIN_MSG_RESUMED")

        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text="▶️ Outbound messaging has been RESUMED.",
        )
        return True

    # -------------------------------------------------
    # SEND
    # -------------------------------------------------
    if upper.startswith("SEND:"):
        if paused:
            logger.warning("ADMIN_MSG_SEND_BLOCKED | paused")
            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text="⚠️ Messaging is PAUSED.",
            )
            return True

        try:
            _, body = text_clean.split(":", 1)
            raw, message = body.strip().split(maxsplit=1)
        except ValueError:
            logger.warning("ADMIN_MSG_SEND_BAD_FORMAT")
            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text="Format: SEND: <number> <message>",
            )
            return True

        contact = (
            db.query(Contact)
            .filter(Contact.contact_number == raw)
            .one_or_none()
        )

        if not contact:
            logger.warning("ADMIN_MSG_SEND_NO_CONTACT | to=%s", raw)
            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text=f"Client {raw} not found.",
            )
            return True

        meta.send_generic_business_update_template(
            to_msisdn=raw,
            blob_text=message,
        )

        logger.info("ADMIN_MSG_SEND_OK | to=%s", raw)

        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text=f"✅ Message sent to {raw}.",
        )
        return True

    # -------------------------------------------------
    # BROADCAST
    # -------------------------------------------------
    if upper.startswith("BROADCAST"):
        if paused:
            logger.warning("ADMIN_MSG_BROADCAST_BLOCKED | paused")
            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text="⚠️ Messaging is PAUSED.",
            )
            return True

        message = ""
        if ":" in text_clean:
            message = text_clean.split(":", 1)[1].strip()

        if not message:
            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text="Format: BROADCAST: <message>",
            )
            return True

        contacts = (
            db.query(Contact)
            .filter(~Contact.contact_number.in_(admin_allowlist))
            .all()
        )

        sent = 0
        for c in contacts:
            meta.send_generic_business_update_template(
                to_msisdn=c.contact_number,
                blob_text=message,
            )
            sent += 1

        logger.info("ADMIN_MSG_BROADCAST_OK | sent=%s", sent)

        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text=f"📣 Broadcast sent to {sent} clients.",
        )
        return True

    logger.debug("ADMIN_MSG_NO_MATCH | text=%r", text_clean)
    return False
