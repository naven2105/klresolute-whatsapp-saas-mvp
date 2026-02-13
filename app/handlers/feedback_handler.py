from __future__ import annotations

"""
File: app/handlers/feedback_handler.py
Project: KLResolute WhatsApp SaaS MVP
"""

import logging

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.outbound.factory import get_meta_client

logger = logging.getLogger("feedback_handler")
logger.setLevel(logging.INFO)


ADMIN_TEMPLATE_NAME = "klr_admin_alert_v1"
CUSTOMER_ACK_TEMPLATE_NAME = "generic_business_update"


# -------------------------------------------------
# Outbound helpers
# -------------------------------------------------

def _send_customer_ack(to_number: str, business_msisdn: str) -> None:
    logger.info(
        "FEEDBACK_ACK_ATTEMPT | customer=%s | template=%s",
        to_number,
        CUSTOMER_ACK_TEMPLATE_NAME,
    )

    try:
        meta = get_meta_client(business_msisdn=business_msisdn)

        result = meta.send_template(
            to_msisdn=to_number,
            template_name=CUSTOMER_ACK_TEMPLATE_NAME,
            language_code="en_US",
            body_params=[
                "🙏 Thank you for your feedback. It has been sent to the manager."
            ],
        )

        logger.info(
            "FEEDBACK_ACK_SENT | customer=%s | status=%s",
            to_number,
            result.status_code,
        )

    except Exception:
        logger.exception(
            "FEEDBACK_ACK_FAIL | customer=%s",
            to_number,
        )


def _send_admin_alert(to_number: str, alert_text: str, business_msisdn: str) -> None:
    logger.info(
        "ADMIN_ALERT_ATTEMPT | admin=%s | template=%s",
        to_number,
        ADMIN_TEMPLATE_NAME,
    )

    try:
        meta = get_meta_client(business_msisdn=business_msisdn)

        result = meta.send_template(
            to_msisdn=to_number,
            template_name=ADMIN_TEMPLATE_NAME,
            language_code="en_US",
            body_params=[alert_text],
        )

        logger.info(
            "ADMIN_ALERT_SENT | admin=%s | status=%s",
            to_number,
            result.status_code,
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
    business_msisdn: str,
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

    _send_customer_ack(sender_number, business_msisdn)

    clean_message = (message_text or "Media received").replace("\n", " ").strip()

    alert_text = (
        f"New feedback received | "
        f"From: {sender_number} | "
        f"Message: {clean_message}"
    )

    if not admin_numbers:
        logger.warning("ADMIN_ALERT_SKIP | reason=no_admin_numbers")
    else:
        logger.info("ADMIN_ALERT_TARGETS | count=%s", len(admin_numbers))

    for admin in admin_numbers:
        _send_admin_alert(admin, alert_text, business_msisdn)

    logger.info("FEEDBACK_COMPLETE | from=%s", sender_number)
    return True
