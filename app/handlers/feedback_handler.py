from __future__ import annotations

"""
File: app/handlers/feedback_handler.py
Project: KLResolute WhatsApp SaaS MVP
"""

import logging

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.messaging.transport import send_template


logger = logging.getLogger("feedback_handler")
logger.setLevel(logging.INFO)


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
        result = send_template(
            to_msisdn=to_number,
            template_name=CUSTOMER_ACK_TEMPLATE_NAME,
            language_code="en_US",
            body_params=[
                "🙏 Thank you for your feedback. It has been sent to the manager."
            ],
        )

        logger.info(
            "FEEDBACK_ACK_SENT | customer=%s | message_id=%s",
            to_number,
            getattr(result, "message_id", None),
        )

    except Exception:
        logger.exception(
            "FEEDBACK_ACK_FAIL | customer=%s",
            to_number,
        )


def _send_admin_alert(to_number: str, alert_text: str) -> None:
    logger.info(
        "ADMIN_ALERT_ATTEMPT | admin=%s | template=%s",
        to_number,
        ADMIN_TEMPLATE_NAME,
    )

    try:
        result = send_template(
            to_msisdn=to_number,
            template_name=ADMIN_TEMPLATE_NAME,
            language_code="en_US",
            body_params=[alert_text],
        )

        logger.info(
            "ADMIN_ALERT_SENT | admin=%s | message_id=%s",
            to_number,
            getattr(result, "message_id", None),
        )

    except Exception:
        logger.exception(
            "ADMIN_ALERT_FAIL | admin=%s",
            to_number,
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

    except Exception:
        logger.exception(
            "FEEDBACK_STORE_FAIL | client_id=%s | from=%s",
            client_id,
            sender_number,
        )
        return True

    _send_customer_ack(sender_number)

    alert_text = (
        f"New feedback received | "
        f"From: {sender_number} | "
        f"Message: {(message_text or 'Media received').replace('\n', ' ').strip()}"
    )

    if not admin_numbers:
        logger.warning("ADMIN_ALERT_SKIP | reason=no_admin_numbers")
    else:
        logger.info("ADMIN_ALERT_TARGETS | count=%s", len(admin_numbers))

    for admin in admin_numbers:
        _send_admin_alert(admin, alert_text)

    logger.info("FEEDBACK_COMPLETE | from=%s", sender_number)
    return True
