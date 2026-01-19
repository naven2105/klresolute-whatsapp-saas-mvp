"""
File: app/handlers/complaint_handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Handle customer complaints (single-step).

LOCKED RULES:
- Trigger: message starts with "complaint:"
- Single message only (no state, no follow-up)
- Complaint saved immediately
- Admin notified immediately
- Customer receives a polite acknowledgement
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
    media_type: str | None = None,
    client_id: str,
    admin_numbers: set[str],
) -> bool:
    """
    Returns:
        True  -> complaint handled
        False -> not a complaint
    """

    if not message_text:
        return False

    raw = message_text.strip()

    # -------------------------------
    # TRIGGER (LOCKED)
    # -------------------------------
    if not raw.lower().startswith("complaint:"):
        return False

    complaint_text = raw.split(":", 1)[1].strip()

    if not complaint_text:
        return True  # prefix sent, no content

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
            "message_text": complaint_text,
            "media_id": media_id,
            "media_type": media_type,
        },
    )
    db.commit()

    # -------------------------------
    # ACK CUSTOMER (POLITE, SHORT)
    # -------------------------------
    _send_text(
        sender_number,
        "Sorry about your issue. The manager will contact you soon."
    )

    # -------------------------------
    # NOTIFY ADMINS
    # -------------------------------
    for admin in admin_numbers:
        _send_text(
            admin,
            f"⚠️ *New Complaint*\n\n"
            f"From: {sender_number}\n"
            f"Client ID: {client_id}\n\n"
            f"Complaint:\n{complaint_text}"
        )

    return True
