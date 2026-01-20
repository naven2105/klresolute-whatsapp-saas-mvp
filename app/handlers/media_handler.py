from __future__ import annotations

"""
File: app/handlers/media_handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Handle admin image messages for SPECIALS.

RULE (LOCKED):
- Admin sends image + caption → treated as SPECIAL
- Stored in specials table
- Replaces previous special (latest wins)
- NOT broadcast to clients
"""

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.outbound.factory import get_meta_client


def handle_media_message(
    *,
    db: Session,
    sender: str,
    msg: dict,
    admin_allowlist: set[str],
    client_id,
) -> bool:
    """
    Returns True if message was handled.
    Returns False if message is NOT an image.
    """

    if msg.get("type") != "image":
        return False

    if sender not in admin_allowlist:
        return True  # silently ignore non-admin images

    media_id = msg["image"]["id"]
    caption = msg["image"].get("caption") or "Today’s specials"

    # -------------------------------
    # Store SPECIAL (latest wins)
    # -------------------------------
    db.execute(
        text(
            """
            INSERT INTO specials (
                client_id,
                media_id,
                caption,
                created_at
            )
            VALUES (
                :client_id,
                :media_id,
                :caption,
                now()
            )
            """
        ),
        {
            "client_id": client_id,
            "media_id": media_id,
            "caption": caption,
        },
    )
    db.commit()

    # Confirm to admin
    meta = get_meta_client()
    meta.send_generic_business_update_template(
        to_msisdn=sender,
        blob_text="Special updated successfully.",
    )

    return True
