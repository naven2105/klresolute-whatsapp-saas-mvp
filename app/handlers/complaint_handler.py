"""
File: app/handlers/complaint_handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Handle customer complaints (Phase 1).

RULES (LOCKED):
- Customer-facing only
- One active complaint per client per day
- Text and images are appended
- No conversation_state
- No schema changes
"""

from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.outbound.meta import MetaWhatsAppClient
from app.outbound.settings import load_meta_settings

_meta = MetaWhatsAppClient(settings=load_meta_settings())


def _notify_admin(admin_numbers, text):
    for admin in admin_numbers:
        _meta.send_session_message(admin, text)


def _get_today_complaint(db: Session, client_id):
    return db.execute(
        text(
            """
            SELECT id
            FROM complaints
            WHERE client_id = :client_id
              AND created_at::date = :today
            ORDER BY created_at DESC
            LIMIT 1
            """
        ),
        {
            "client_id": client_id,
            "today": date.today(),
        },
    ).first()


def handle_complaint_message(
    *,
    db: Session,
    sender_number: str,
    message_text: str,
    media_id: str | None,
    client_id,
    admin_numbers,
) -> bool:
    """
    Starts a complaint ONLY if none exists today.
    """

    keyword = (message_text or "").strip().upper()
    if keyword not in ("COMPLAINT", "ISSUE", "PROBLEM"):
        return False

    existing = _get_today_complaint(db, client_id)
    if existing:
        # Complaint already active → do nothing
        return True

    db.execute(
        text(
            """
            INSERT INTO complaints (
                client_id,
                description,
                media_id,
                created_at
            )
            VALUES (
                :client_id,
                :description,
                :media_id,
                now()
            )
            """
        ),
        {
            "client_id": client_id,
            "description": f"Complaint opened by {sender_number}",
            "media_id": media_id,
        },
    )
    db.commit()

    _meta.send_session_message(
        sender_number,
        "📩 Please describe your issue.\nYou may also send a photo.",
    )

    _notify_admin(
        admin_numbers,
        f"⚠️ New complaint started\nFrom: {sender_number}",
    )

    return True


def record_complaint_detail(
    *,
    db: Session,
    sender_number: str,
    message_text: str | None,
    media_id: str | None,
    admin_numbers,
    client_id,
) -> bool:
    """
    Appends detail to today’s complaint.
    """

    row = _get_today_complaint(db, client_id)
    if not row:
        return False

    updates = []
    if message_text:
        updates.append(f"\nTEXT: {message_text}")
    if media_id:
        updates.append(f"\nIMAGE_ID: {media_id}")

    if not updates:
        return False

    db.execute(
        text(
            """
            UPDATE complaints
            SET description = description || :append_text
            WHERE id = :id
            """
        ),
        {
            "append_text": "".join(updates),
            "id": row[0],
        },
    )
    db.commit()

    _notify_admin(
        admin_numbers,
        f"📨 Complaint update from {sender_number}",
    )

    return True
