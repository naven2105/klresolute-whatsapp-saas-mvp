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

from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.outbound.meta import MetaWhatsAppClient
from app.outbound.settings import load_meta_settings


# -------------------------------------------------
# Setup
# -------------------------------------------------

_meta_client = MetaWhatsAppClient(settings=load_meta_settings())

ADMIN_TEMPLATE_NAME = "klr_admin_alert_v1"


def _send_text(to_number: str, text_msg: str) -> None:
    _meta_client.send_session_message(
        to_msisdn=to_number,
        text=text_msg,
    )


def _send_admin_template(to_number: str, alert_text: str) -> None:
    _meta_client.send_template_message(
        to_msisdn=to_number,
        template_name=ADMIN_TEMPLATE_NAME,
        language="en_US",
        components=[
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "text": alert_text}
                ],
            }
        ],
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
    _send_text(
        sender_number,
        "🙏 Thank you. Your complaint has been sent to the manager.",
    )

    # -------------------------------
    # Notify admins (TEMPLATE ONLY)
    # -------------------------------
    alert_text = (
        f"New complaint received\n"
        f"From: {sender_number}\n"
        f"Message: {message_text or '[Media received]'}"
    )

    for admin in admin_numbers:
        _send_admin_template(admin, alert_text)

    return True
