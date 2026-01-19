"""
File: app/handlers/complaint_handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Handle customer complaints.

RULES (LOCKED):
- Customer-facing only
- NO use of conversation_state
- One-pass submission (text or image)
- Complaint is immediately stored
- Admin is notified
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
    media_id: str | None,
    client_id: str,
    admin_numbers: set[str],
) -> bool:
    """
    Handle a customer complaint message.

    Returns:
        True  -> complaint handled here
        False -> not a complaint message
    """

    text_norm = (message_text or "").strip().upper()

    # ----------------------------------
    # ENTRY TRIGGER
    # ----------------------------------
    if text_norm not in {"COMPLAINT", "COMPLAIN", "ISSUE", "PROBLEM"}:
        return False

    # Ask customer to describe issue
    _send_text(
        sender_number,
        "📝 Please describe your issue.\n"
        "You may also send a photo."
    )

    # Insert placeholder complaint record
    db.execute(
        text(
            """
            INSERT INTO complaints (
                client_id,
                sender_msisdn,
                description,
                media_id,
                created_at
            )
            VALUES (
                :client_id,
                :sender,
                NULL,
                NULL,
                now()
            )
            """
        ),
        {
            "client_id": client_id,
            "sender": sender_number,
        },
    )
    db.commit()

    return True


def record_complaint_detail(
    *,
    db: Session,
    sender_number: str,
    message_text: str | None,
    media_id: str | None,
    admin_numbers: set[str],
) -> bool:
    """
    Records the actual complaint content (text or image).
    Called AFTER the prompt.
    """

    # Get latest unresolved complaint
    complaint = db.execute(
        text(
            """
            SELECT id
            FROM complaints
            WHERE sender_msisdn = :sender
              AND resolved = false
            ORDER BY created_at DESC
            LIMIT 1
            """
        ),
        {"sender": sender_number},
    ).mappings().first()

    if not complaint:
        return False

    # Update complaint
    db.execute(
        text(
            """
            UPDATE complaints
            SET description = COALESCE(:desc, description),
                media_id = COALESCE(:media, media_id)
            WHERE id = :id
            """
        ),
        {
            "id": complaint["id"],
            "desc": message_text,
            "media": media_id,
        },
    )
    db.commit()

    # Notify admin(s)
    admin_msg = (
        "🚨 *New Customer Complaint*\n\n"
        f"From: {sender_number}\n"
        f"Message: {message_text or '[Photo attached]'}"
    )

    for admin in admin_numbers:
        _send_text(admin, admin_msg)

    # Confirm to customer
    _send_text(
        sender_number,
        "✅ Thank you. Your complaint has been sent to management."
    )

    return True
