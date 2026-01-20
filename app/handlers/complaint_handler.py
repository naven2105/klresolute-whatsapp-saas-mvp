"""
File: app/handlers/complaint_handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Handle customer complaints.

RULES (LOCKED):
- Customer-facing only
- Stores complaint immediately
- Supports text and optional image
- ALWAYS notifies admin allowlist
- No assumptions about schema beyond complaints table
"""

from __future__ import annotations

import os
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.outbound.meta import MetaWhatsAppClient
from app.outbound.settings import load_meta_settings


# -------------------------------------------------
# Setup
# -------------------------------------------------

_meta_client = MetaWhatsAppClient(settings=load_meta_settings())

ADMIN_ALLOWLIST = {
    n.strip()
    for n in os.getenv("OUTBOUND_TEST_ALLOWLIST", "").split(",")
    if n.strip()
}


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
    client_id,
    msg: dict,
) -> bool:
    """
    Handles complaint capture and admin notification.

    Returns:
        True  -> complaint handled
        False -> not a complaint message
    """

    msg_type = msg.get("type")

    # -------------------------------
    # Extract complaint content
    # -------------------------------
    message_text: Optional[str] = None
    media_id: Optional[str] = None
    media_type: Optional[str] = None

    if msg_type == "text":
        message_text = msg["text"]["body"].strip()

    elif msg_type == "image":
        media_id = msg["image"]["id"]
        media_type = "image"
        message_text = msg["image"].get("caption")

    else:
        return False  # not supported → ignore

    # -------------------------------
    # Store complaint
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
        "🙏 Thank you for letting us know.\n"
        "Your complaint has been sent to the manager.",
    )

    # -------------------------------
    # Notify admin(s)
    # -------------------------------
    admin_alert = (
        "⚠️ *New Complaint Received*\n\n"
        f"From: {sender_number}\n"
        f"Text: {message_text or '[Photo sent]'}"
    )

    for admin in ADMIN_ALLOWLIST:
        _send_text(admin, admin_alert)

    return True
