from __future__ import annotations

"""
File: app/clients/pilateshq/feedback/handler.py
Project: KLResolute WhatsApp SaaS MVP

Sprint 13 – Client Feedback Isolation (PilatesHQ)

Purpose:
PilatesHQ-specific feedback handler.

Notes:
- Behaviour identical to legacy shared handler
- No logic changes
- No schema changes
- Client-isolated ownership
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.outbound.factory import get_meta_client
from app.messaging.template_registry import PHQ_ADMIN_ALERT

logger = logging.getLogger("pilateshq.feedback")

ADMIN_TEMPLATE_NAME = PHQ_ADMIN_ALERT
CUSTOMER_ACK_TEMPLATE_NAME = PHQ_ADMIN_ALERT


# -------------------------------------------------
# Outbound helpers
# -------------------------------------------------

def _send_customer_ack(
    db: Session,
    to_number: str,
    business_msisdn: str,
) -> None:
    try:
        meta = get_meta_client(
            db=db,
            business_msisdn=business_msisdn,
        )

        meta.send_template(
            to_msisdn=to_number,
            template_name=CUSTOMER_ACK_TEMPLATE_NAME,
            language_code="en_US",
            body_params=[
                "🙏 Thank you for your feedback. It has been sent to the manager."
            ],
        )

    except Exception:
        logger.exception("FEEDBACK_ACK_FAIL | customer=%s", to_number)


def _send_admin_alert(
    db: Session,
    to_number: str,
    alert_text: str,
    business_msisdn: str,
) -> None:
    try:
        meta = get_meta_client(
            db=db,
            business_msisdn=business_msisdn,
        )

        meta.send_template(
            to_msisdn=to_number,
            template_name=ADMIN_TEMPLATE_NAME,
            language_code="en_US",
            body_params=[alert_text],
        )

    except Exception:
        logger.exception("ADMIN_ALERT_FAIL | admin=%s", to_number)


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

    if not message_text and not media_id:
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

    except Exception:
        logger.exception("FEEDBACK_STORE_FAIL")
        return True

    _send_customer_ack(db, sender_number, business_msisdn)

    clean_message = (message_text or "Media received").replace("\n", " ").strip()

    alert_text = (
        f"New feedback received | "
        f"From: {sender_number} | "
        f"Message: {clean_message}"
    )

    for admin in admin_numbers:
        _send_admin_alert(db, admin, alert_text, business_msisdn)

    return True