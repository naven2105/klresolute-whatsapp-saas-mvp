from __future__ import annotations

"""
File: app/handlers/admin_messaging.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Handle admin messaging & system commands ONLY.

Responsibilities:
- PAUSE / RESUME outbound
- SEND: <number> <message>
- BROADCAST: <message>   (text only)
- COUNT clients

Rules:
- Admin-only
- Always acknowledge admin
- Never handle surveys
"""

import logging
import re
from sqlalchemy.orm import Session

from app.models import Contact
from app.outbound.factory import get_meta_client

# -------------------------------------------------
# Logging
# -------------------------------------------------
logger = logging.getLogger("admin_messaging")


# -------------------------------------------------
# Helpers
# -------------------------------------------------
def _normalise_msisdn(raw: str | None) -> str | None:
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("0"):
        digits = "27" + digits[1:]
    if digits.startswith("27") and len(digits) >= 11:
        return digits
    return None


# -------------------------------------------------
# Handler
# -------------------------------------------------
def handle_admin_messaging(
    *,
    db: Session,
    sender_number: str,
    message_text: str,
    admin_allowlist: set[str],
) -> bool:
    """
    Returns:
        True  -> handled here
        False -> not a messaging command
    """

    logger.info(
        "ADMIN_MSG_ENTER | sender=%s | text=%r",
        sender_number,
        message_text,
    )

    meta = get_meta_client()
    upper = message_text.upper()

    paused = getattr(meta, "is_paused", False)
    logger.info("ADMIN_MSG_PAUSE_STATE | paused=%s", paused)

    # -----------------------------
    # PAUSE
    # -----------------------------
    if upper == "PAUSE":
        meta.is_paused = True
        logger.info("ADMIN_MSG_PAUSED")

        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text="⏸️ Outbound messaging is now PAUSED.",
        )
        return True

    # -----------------------------
    # RESUME
    # -----------------------------
    if upper == "RESUME":
        meta.is_paused = False
        logger.info("ADMIN_MSG_RESUMED")

        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text="▶️ Outbound messaging has been RESUMED.",
        )
        return True

    # -----------------------------
    # COUNT
    # -----------------------------
    if upper == "COUNT":
        count = db.query(Contact).count()
        logger.info("ADMIN_MSG_COUNT | count=%s", count)

        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text=f"👥 Active clients: {count}",
        )
        return True

    # -----------------------------
    # SEND: <number> <message>
    # -----------------------------
    if upper.startswith("SEND:"):
        if paused:
            logger.warning("ADMIN_MSG_SEND_BLOCKED | paused")
            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text="⚠️ Outbound messaging is PAUSED.",
            )
            return True

        try:
            _, body = message_text.split(":", 1)
            raw_number, text_msg = body.strip().split(maxsplit=1)
            msisdn = _normalise_msisdn(raw_number)

            if not msisdn:
                raise ValueError("Invalid MSISDN")

            contact = (
                db.query(Contact)
                .filter(Contact.contact_number == msisdn)
                .one_or_none()
            )
            if not contact:
                raise ValueError("Contact not found")

            meta.send_generic_business_update_template(
                to_msisdn=msisdn,
                blob_text=text_msg.strip(),
            )

            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text=f"✅ Message sent to {msisdn}.",
            )

            logger.info("ADMIN_MSG_SEND_OK | to=%s", msisdn)

        except Exception as exc:
            logger.error(
                "ADMIN_MSG_SEND_FAIL | error=%s",
                exc,
                exc_info=True,
            )
            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text="❌ SEND failed. Format: SEND: <number> <message>",
            )

        return True

    # -----------------------------
    # BROADCAST: <message>
    # -----------------------------
    if upper.startswith("BROADCAST"):
        if paused:
            logger.warning("ADMIN_MSG_BROADCAST_BLOCKED | paused")
            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text="⚠️ Outbound messaging is PAUSED.",
            )
            return True

        text_msg = ""
        if ":" in message_text:
            text_msg = message_text.split(":", 1)[1].strip()

        contacts = (
            db.query(Contact)
            .filter(~Contact.contact_number.in_(admin_allowlist))
            .all()
        )

        sent = 0
        failed = 0

        for c in contacts:
            try:
                meta.send_generic_business_update_template(
                    to_msisdn=c.contact_number,
                    blob_text=text_msg,
                )
                sent += 1
            except Exception as exc:
                failed += 1
                logger.error(
                    "ADMIN_MSG_BROADCAST_FAIL | to=%s | error=%s",
                    c.contact_number,
                    exc,
                    exc_info=True,
                )

        logger.info(
            "ADMIN_MSG_BROADCAST_DONE | sent=%s | failed=%s",
            sent,
            failed,
        )

        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text=f"📣 Broadcast sent to {sent} clients.",
        )

        return True

    # -----------------------------
    # Not handled here
    # -----------------------------
    logger.info("ADMIN_MSG_SKIP | not a messaging command")
    return False
