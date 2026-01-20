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


def _send_customer_ack(to_number: str) -> None:
    try:
        _meta_client.send_session_message(
            to_msisdn=to_number,
            text="🙏 Thank you. Your feedback has been sent to the manager.",
        )
        logger.info("Customer ACK sent to %s", to_number)
    except Exception as exc:
        logger.error(
            "FAILED to send customer ACK to %s | error=%s",
            to_number,
            exc,
            exc_info=True,
        )


def _send_admin_alert(to_number: str, alert_text: str) -> None:
    logger.info(
        "Attempting admin template send | admin_msisdn=%s | template=%s",
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
            "Admin template send result | admin=%s | result=%s",
            to_number,
            result,
        )

    except Exception as exc:
        logger.error(
            "FAILED admin template send | admin=%s | error=%s",
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

    # Nothing to store
    if not message_text and not media_id:
        logger.info("feedback ignored (no text / no media)")
        return False

    # -------------------------------
    # Store feedback (schema-aligned)
    # -------------------------------
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
        "feedback stored | client_id=%s | from=%s",
        client_id,
        sender_number,
    )

    # -------------------------------
    # Acknowledge customer (session)
    # -------------------------------
    _send_customer_ack(sender_number)

    # -------------------------------
    # Notify admins (TEMPLATE ONLY)
    # -------------------------------
    alert_text = (
        f"New feedback received | "
        f"From: {sender_number} | "
        f"Message: {message_text or 'Media received'}"
    )

    if not admin_numbers:
        logger.warning("No admin numbers configured for feedback alert")
    else:
        logger.info("Admin alert target count = %s", len(admin_numbers))

    for admin in admin_numbers:
        _send_admin_alert(admin, alert_text)

    return True
