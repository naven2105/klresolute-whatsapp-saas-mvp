from __future__ import annotations

"""
File: app/handlers/complaint_handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Handle customer complaints.

RULES (LOCKED):
- Customer-facing only
- Append-only (no updates)
- Stores into complaints table (existing schema)
- ALL admin notifications use Meta template klr_admin_alert_v1
"""

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.outbound.meta import MetaWhatsAppClient
from app.outbound.settings import load_meta_settings


# -------------------------------------------------
# Setup
# -------------------------------------------------

_meta_client = MetaWhatsAppClient(settings=load_meta_settings())

ADMIN_TEMPLATE_NAME = "klr_admin_alert_v1"


def _send_customer_ack(to_number: str) -> None:
    _meta_client.send_session_message(
        to_msisdn=to_number,
        text="🙏 Thank you. Your complaint has been sent to the manager.",
    )


def _send_admin_alert(to_number: str, alert_text: str) -> None:
    _meta_client.send_template(
        to_msisdn=to_number,
        template_name=ADMIN_TEMPLATE_NAME,
        language_code="en_US",
        body_params=[alert_text],
    )


# -------------------------------------------------
# Handler
# -------------------------------------------------

def handle_complaint_message(
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
    Stores complaint and notifies admin via template.

    Returns:
        True  -> complaint handled
        False -> ignore
    """

    # Nothing to store
    if not message_text and not media_id:
        return False

    # -------------------------------
    # Store complaint (schema-aligned)
    # -------------------------------
    db.execute(
        text(
            """
            INSERT INTO complaints (
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

    # -------------------------------
    # Acknowledge customer (session)
    # -------------------------------
    _send_customer_ack(sender_number)

    # -------------------------------
    # Notify admins (TEMPLATE ONLY)
    # -------------------------------
    alert_text = (
        f"New complaint received\n"
        f"From: {sender_number}\n"
        f"Message: {message_text or 'Media received'}"
    )

    for admin in admin_numbers:
        _send_admin_alert(admin, alert_text)

    return True   
