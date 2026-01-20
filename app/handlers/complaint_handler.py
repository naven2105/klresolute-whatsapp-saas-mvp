"""
File: app/handlers/complaint_handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Handle customer complaints.

RULES (LOCKED):
- Customer-facing only
- Append-only (no updates)
- Supports text complaints (Phase 1)
- Stores into complaints table (existing schema)
- ALWAYS notifies admin allowlist
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


def _send_text(to_number: str, text_msg: str) -> None:
    _meta_client.send_session_message(
        to_msisdn=to_number,
        text=text_msg,
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
    Stores complaint and notifies admin.

    Returns:
        True  -> complaint handled
        False -> ignore
    """

    # Ignore empty complaints
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
    # Acknowledge customer
    # -------------------------------
    _send_text(
        sender_number,
        "🙏 Thank you. Your complaint has been sent to the manager.",
    )

    # -------------------------------
    # Notify admins
    # -------------------------------
    admin_msg = (
        "⚠️ *New Customer Complaint*\n\n"
        f"From: {sender_number}\n"
        f"Message: {message_text or '[Media received]'}"
    )

    for admin in admin_numbers:
        _send_text(admin, admin_msg)

    return True
