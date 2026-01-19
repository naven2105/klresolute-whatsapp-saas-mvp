"""
File: app/handlers/complaint_handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Handle customer complaints.

RULES (LOCKED):
- Append-only (1 row per message)
- Prompt shown ONLY on keyword
- Uses complaints table AS-IS
- No conversation_state
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
    Handle complaint-related messages.
    """

    text_norm = (message_text or "").strip().upper()

    # 1️⃣ Trigger only — show prompt, DO NOT store row
    if text_norm in TRIGGERS:
        _meta.send_session_message(
            sender_number,
            "📩 Please describe your issue.\nYou may also send a photo.",
        )
        return True

    # 2️⃣ Store actual complaint content
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
                f"⚠️ Complaint from {sender_number}",
            )

        return True

    return False
