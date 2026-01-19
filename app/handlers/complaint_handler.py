"""
File: app/handlers/complaint_handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Handle customer complaints.

RULES (LOCKED):
- Customer-facing
- One complaint per conversation
- Complaint is saved immediately
- Admin is notified on creation
"""

from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.outbound.meta import MetaWhatsAppClient
from app.outbound.settings import load_meta_settings

_meta_client = MetaWhatsAppClient(settings=load_meta_settings())


def _send_text(to_number: str, text: str) -> None:
    _meta_client.send_session_message(
        to_msisdn=to_number,
        text=text,
    )


def handle_complaint_message(
    *,
    db: Session,
    sender_number: str,
    message_text: str | None,
    media_id: str | None = None,
    client_id: str,
    admin_numbers: set[str],
) -> bool:
    """
    Entry point for complaint handling.

    Returns:
        True  -> complaint handled
        False -> not a complaint message
    """

    text_norm = (message_text or "").strip()

    # -------------------------------
    # TRIGGER
    # -------------------------------
    if text_norm.upper() not in {"COMPLAINT", "COMPLAINTS"}:
        return False

    # -------------------------------
    # SAVE COMPLAINT
    # -------------------------------
    db.execute(
        text(
            """
            INSERT INTO complaints (
                client_id,
                customer_msisdn,
                message_text,
                media_id,
                created_at
            )
            VALUES (
                :client_id,
                :customer_msisdn,
                :message_text,
                :media_id,
                now()
            )
            """
        ),
        {
            "client_id": client_id,
            "customer_msisdn": sender_number,
            "message_text": message_text or "Complaint opened",
            "media_id": media_id,
        },
    )
    db.commit()

    # -------------------------------
    # ACK CUSTOMER
    # -------------------------------
    _send_text(
        sender_number,
        "🙏 Thank you. Your complaint has been logged.\n"
        "A manager will review it shortly."
    )

    # -------------------------------
    # NOTIFY ADMINS
    # -------------------------------
    for admin in admin_numbers:
        _send_text(
            admin,
            f"⚠️ *New Complaint*\n\n"
            f"From: {sender_number}\n"
            f"Client ID: {client_id}"
        )

    return True
