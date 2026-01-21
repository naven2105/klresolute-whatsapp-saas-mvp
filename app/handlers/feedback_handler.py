from __future__ import annotations

"""
File: app/handlers/feedback_handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Handle customer feedbacks.

RULES (LOCKED):
- Customer-facing only
- Append-only (no updates)
- Stores into feedbacks table (existing schema)
- ALL admin notifications use Meta template klr_admin_alert_v1
"""

import logging

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.outbound.meta import MetaWhatsAppClient
from app.outbound.settings import load_meta_settings


# -------------------------------------------------
# Logging
# -------------------------------------------------

logger = logging.getLogger("feedback_handler")
logger.setLevel(logging.INFO)


# -------------------------------------------------
# Setup
# -------------------------------------------------

_meta_client = MetaWhatsAppClient(settings=load_meta_settings())

ADMIN_TEMPLATE_NAME = "klr_admin_alert_v1"
CUSTOMER_ACK_TEMPLATE_NAME = "generic_business_update"


# -------------------------------------------------
# Outbound helpers
# -------------------------------------------------

def _send_customer_ack(to_number: str) -> None:
    logger.info(
        "FEEDBACK_ACK_ATTEMPT | customer=%s | template=%s",
        to_number,
        CUSTOMER_ACK_TEMPLATE_NAME,
    )

    try:
        result = _meta_client.send_template(
            to_msisdn=to_number,
            template_name=CUSTOMER_ACK_TEMPLATE_NAME,
            language_code="en_US",
            body_params=[
                "🙏 Thank you for your feedback. It has been sent to the manager."
            ],
        )

        logger.info(
            "FEEDBACK_ACK_SENT | customer=%s | result=%s",
            to_number,
            result,
        )

    except Exception as exc:
        logger.error(
            "FEEDBACK_ACK_FAIL | customer=%s | error=%s",
            to_number,
            exc,
            exc_info=True,
        )


def _send_admin_alert(to_number: str, alert_text: str) -> None:
    logger.info(
        "ADMIN_ALERT_ATTEMPT | admin=%s | template=%s",
        to_number,
        ADMIN_TEMPLATE_NAME,
    )

    try:
        result = _meta_client.send_template(
            to_msisdn=to_number,
            template_name=ADMIN_TEMPLATE_NAME,
            language_code="en_US",
            body_params=[alert_text],
        )

        logger.info(
            "ADMIN_ALERT_SENT | admin=%s | result=%s",
            to_number,
            result,
        )

    except Exception as exc:
        logger.error(
            "ADMIN_ALERT_FAIL | admin=%s | error=%s",
            to_number,
            exc,
            exc_info=True,
        )


# -------------------------------------------------
# Handler
# -------------------------------------------------

def handle_feedback_message(
    *,
    db: Session,
    sender_number: str,
    message_text: str | None,
    media_id: str | None,
    media_type: str | None,
    client_id,
    admin_numbers: set[str],
) -> bool:
    """
    Stores feedback and notifies admin via template.

    Returns:
        True  -> feedback handled
        False -> ignore
    """

    logger.info(
        "FEEDBACK_ENTER | from=%s | client_id=%s | has_text=%s | has_media=%s",
        sender_number,
        client_id,
        bool(message_text),
        bool(media_id),
    )

    if not message_text and not media_id:
        logger.info("FEEDBACK_IGNORED | reason=no_text_no_media")
        return False

    # -------------------------------
    # Store feedback
    # -------------------------------
    try:
        db.execute(
            text(
                """
                INSERT INTO feedbacks (
                    client_id,
                    customer_msisdn,
                    message_text,
                    media_id,
                    media_type,
                    created_at
                )
                VALUES (
                    :client_id,
                    :customer_msisdn,
                    :message_text,
                    :media_id,
                    :media_type,
                    now()
                )
                """
            ),
            {
                "client_id": client_id,
                "customer_msisdn": sender_number,
                "message_text": message_text,
                "media_id": media_id,
                "media_type": media_type,
            },
        )
        db.commit()

        logger.info(
            "FEEDBACK_STORED | client_id=%s | from=%s",
            client_id,
            sender_number,
        )

    except Exception as exc:
        logger.error(
            "FEEDBACK_STORE_FAIL | client_id=%s | from=%s | error=%s",
            client_id,
            sender_number,
            exc,
            exc_info=True,
        )
        return True  # still handled, but logged

    # -------------------------------
    # Customer acknowledgement (TEMPLATE)
    # -------------------------------
    _send_customer_ack(sender_number)

    # -------------------------------
    # Admin notification (TEMPLATE)
    # -------------------------------
    alert_text = (
        f"New feedback received\n"
        f"From: {sender_number}\n"
        f"Message: {message_text or 'Media received'}"
    )

    if not admin_numbers:
        logger.warning("ADMIN_ALERT_SKIP | reason=no_admin_numbers")
    else:
        logger.info("ADMIN_ALERT_TARGETS | count=%s", len(admin_numbers))

    for admin in admin_numbers:
        _send_admin_alert(admin, alert_text)

    logger.info("FEEDBACK_COMPLETE | from=%s", sender_number)
    return True
