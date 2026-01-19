"""
File: app/handlers/complaint_handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Handle customer complaints (single-pass).

RULES (LOCKED):
- Customer-facing only
- Triggered by keyword
- One message capture
- Forward to admin
- Store in DB
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
    message_text: str,
    msg: dict,
    client_id: str,
    admin_msisdn: str,
) -> bool:

    upper = (message_text or "").strip().upper()

    # 1️⃣ Trigger
    if upper in TRIGGERS:
        _meta.send_session_message(
            to_msisdn=sender_number,
            text="Please describe your issue.\nYou may also send a photo.",
        )

        db.execute(
            text(
                """
                INSERT INTO conversation_state (
                    sender_msisdn,
                    client_id,
                    state_type,
                    active
                )
                VALUES (
                    :sender,
                    :client_id,
                    'COMPLAINT',
                    true
                )
                """
            ),
            {"sender": sender_number, "client_id": client_id},
        )
        db.commit()
        return True

    # 2️⃣ Capture
    row = db.execute(
        text(
            """
            SELECT id
            FROM conversation_state
            WHERE sender_msisdn = :sender
              AND state_type = 'COMPLAINT'
              AND active = true
            LIMIT 1
            """
        ),
        {"sender": sender_number},
    ).first()

    if not row:
        return False

    media_id = None
    media_type = None

    if msg.get("type") == "image":
        media_id = msg["image"]["id"]
        media_type = "image"

    db.execute(
        text(
            """
            INSERT INTO complaints (
                client_id,
                customer_msisdn,
                message_text,
                media_id,
                media_type
            )
            VALUES (
                :client_id,
                :customer,
                :text,
                :media_id,
                :media_type
            )
            """
        ),
        {
            "client_id": client_id,
            "customer": sender_number,
            "text": message_text if msg.get("type") == "text" else None,
            "media_id": media_id,
            "media_type": media_type,
        },
    )

    db.execute(
        text(
            """
            UPDATE conversation_state
            SET active = false,
                completed_at = now()
            WHERE id = :id
            """
        ),
        {"id": row.id},
    )

    db.commit()

    _meta.send_session_message(
        to_msisdn=admin_msisdn,
        text=(
            "⚠️ New Customer Complaint\n\n"
            f"From: {sender_number}\n\n"
            f"{message_text or '[Image attached]'}"
        ),
    )

    _meta.send_session_message(
        to_msisdn=sender_number,
        text="Thank you. Your message has been sent to the manager.",
    )

    return True
