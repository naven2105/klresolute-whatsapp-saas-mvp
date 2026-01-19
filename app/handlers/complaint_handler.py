"""
File: app/handlers/complaint_handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Handle customer complaints (Phase 1).

RULES (LOCKED):
- Customer-facing only
- One complaint row per message (simple + safe)
- Uses existing complaints table AS-IS
- No conversation_state
- No schema changes
"""

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.outbound.meta import MetaWhatsAppClient
from app.outbound.settings import load_meta_settings

_meta = MetaWhatsAppClient(settings=load_meta_settings())

TRIGGERS = {"COMPLAINT", "ISSUE", "PROBLEM"}


def handle_complaint_message(
    *,
    db: Session,
    sender_number: str,
    message_text: str | None,
    media_id: str | None,
    media_type: str | None,
    client_id,
    admin_numbers,
) -> bool:
    """
    Creates a complaint record.
    """

    keyword = (message_text or "").strip().upper()

    # Start complaint
    if keyword in TRIGGERS:
        _meta.send_session_message(
            sender_number,
            "📩 Please describe your issue.\nYou may also send a photo.",
        )
        return True

    # Record complaint detail (text or media)
    if message_text or media_id:
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
                    :msisdn,
                    :message_text,
                    :media_id,
                    :media_type,
                    now()
                )
                """
            ),
            {
                "client_id": client_id,
                "msisdn": sender_number,
                "message_text": message_text,
                "media_id": media_id,
                "media_type": media_type,
            },
        )
        db.commit()

        for admin in admin_numbers:
            _meta.send_session_message(
                admin,
                f"⚠️ New complaint received from {sender_number}",
            )

        return True

    return False
