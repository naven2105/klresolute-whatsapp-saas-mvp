"""
File: app/handlers/complaint_handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Handle customer complaints.

RULES (LOCKED):
- Customer-facing
- No conversation_state
- Persist immediately
- Forward to admin immediately
"""

from __future__ import annotations

import os
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.outbound.meta import MetaWhatsAppClient
from app.outbound.settings import load_meta_settings


_meta = MetaWhatsAppClient(settings=load_meta_settings())

ADMIN_ALLOWLIST = {
    n.strip()
    for n in os.getenv("OUTBOUND_TEST_ALLOWLIST", "").split(",")
    if n.strip()
}


def _send_text(to: str, text_msg: str) -> None:
    _meta.send_session_message(
        to_msisdn=to,
        text=text_msg,
    )


def handle_complaint_message(
    *,
    db: Session,
    sender_number: str,
    message_text: Optional[str],
    media_id: Optional[str],
    media_type: Optional[str],
    client_id,
) -> bool:
    """
    Returns:
        True -> complaint handled
        False -> not a complaint
    """

    text_norm = (message_text or "").strip().upper()

    # ---------------------------
    # START COMPLAINT
    # ---------------------------
    if text_norm == "COMPLAINT":
        _send_text(
            sender_number,
            "📝 Please describe your issue.\nYou may also send a photo.",
        )
        return True

    # ---------------------------
    # SAVE COMPLAINT DETAIL
    # ---------------------------
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

        # ---------------------------
        # FORWARD TO ADMIN(S)
        # ---------------------------
        admin_text = (
            "🚨 *New Customer Complaint*\n\n"
            f"From: {sender_number}\n"
            f"Message: {message_text or '[media only]'}"
        )

        for admin in ADMIN_ALLOWLIST:
            _send_text(admin, admin_text)

        _send_text(
            sender_number,
            "✅ Thank you. Your complaint has been sent to management.",
        )
        return True

    return False
