from __future__ import annotations

"""
File: app/handlers/admin_messaging.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Admin messaging commands only.

Scope (LOCKED):
- SEND
- BROADCAST
- PAUSE / RESUME outbound
- NO surveys
- NO admin menu text

Rules:
- Admin-facing only
- Explicit logging for every decision
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

logger = logging.getLogger("admin_messaging")


# -------------------------------------------------
# Entry point
# -------------------------------------------------

def handle_admin_messaging(
    *,
    db: Session,
    sender_number: str,
    message_text: str,
    business_msisdn: str,
) -> bool:
    """
    Handles admin messaging commands.

    Returns:
        True  -> command handled
        False -> not a messaging command
    """

    logger.info(
        "ADMIN_MSG_ENTER | sender=%s | raw=%r",
        sender_number,
        message_text,
    )

    
    if not is_admin_message(
        db=db,
        sender=sender_number,
        business_msisdn=business_msisdn,
    ):
        logger.info(
            "ADMIN_MSG_REJECT | sender not admin | sender=%s",
            sender_number,
        )
        return False    

    meta = get_meta_client()
    text = (message_text or "").strip()
    upper = text.upper()

    # -------------------------------------------------
    # PAUSE outbound
    # -------------------------------------------------
    if upper == "PAUSE":
        logger.info("ADMIN_MSG_PAUSE_REQUEST")

        try:
            meta.is_paused = True
            logger.info("ADMIN_MSG_PAUSED_OK")
            meta.send_session_message(
                to_msisdn=sender_number,
                text="⏸️ Outbound messaging paused.",
            )
        except Exception as exc:
            logger.error(
                "ADMIN_MSG_PAUSE_FAIL | error=%s",
                exc,
                exc_info=True,
            )
        return True

    # -------------------------------------------------
    # RESUME outbound
    # -------------------------------------------------
    if upper == "RESUME":
        logger.info("ADMIN_MSG_RESUME_REQUEST")

        try:
            meta.is_paused = False
            logger.info("ADMIN_MSG_RESUMED_OK")
            meta.send_session_message(
                to_msisdn=sender_number,
                text="▶️ Outbound messaging resumed.",
            )
        except Exception as exc:
            logger.error(
                "ADMIN_MSG_RESUME_FAIL | error=%s",
                exc,
                exc_info=True,
            )
        return True

    # -------------------------------------------------
    # SEND: <number> <message>
    # -------------------------------------------------
    if upper.startswith("SEND "):
        logger.info("ADMIN_MSG_SEND_REQUEST")

        parts = text.split(maxsplit=2)
        if len(parts) < 3:
            logger.warning("ADMIN_MSG_SEND_INVALID_SYNTAX")
            meta.send_session_message(
                to_msisdn=sender_number,
                text="❗ Usage: SEND <number> <message>",
            )
            return True

        _, to_number, body = parts

        try:
            meta.send_session_message(
                to_msisdn=to_number,
                text=body,
            )
            logger.info(
                "ADMIN_MSG_SEND_OK | to=%s",
                to_number,
            )
            meta.send_session_message(
                to_msisdn=sender_number,
                text=f"✅ Message sent to {to_number}",
            )
        except Exception as exc:
            logger.error(
                "ADMIN_MSG_SEND_FAIL | to=%s | error=%s",
                to_number,
                exc,
                exc_info=True,
            )
            meta.send_session_message(
                to_msisdn=sender_number,
                text="⚠️ Send failed (see logs).",
            )
        return True

    # -------------------------------------------------
    # BROADCAST: <message>
    # -------------------------------------------------
    if upper.startswith("BROADCAST "):
        logger.info("ADMIN_MSG_BROADCAST_REQUEST")

        body = text[len("BROADCAST ") :].strip()
        if not body:
            logger.warning("ADMIN_MSG_BROADCAST_EMPTY")
            meta.send_session_message(
                to_msisdn=sender_number,
                text="❗ Usage: BROADCAST <message>",
            )
            return True


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

        contacts = (
            db.query(Contact)
            .filter(~Contact.contact_number.in_(admin_numbers))
            .all()
        )


        logger.info(
            "ADMIN_MSG_BROADCAST_BEGIN | recipients=%s",
            len(contacts),
        )

        sent = 0
        failed = 0

        for c in contacts:
            try:
                meta.send_generic_business_update_template(
                    to_msisdn=c.contact_number,
                    blob_text=body,
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

        meta.send_session_message(
            to_msisdn=sender_number,
            text=f"📣 Broadcast complete. Sent={sent}, Failed={failed}",
        )
        return True

    # -------------------------------------------------
    # Not handled here
    # -------------------------------------------------
    logger.debug("ADMIN_MSG_FALLTHROUGH")
    return False
