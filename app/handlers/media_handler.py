from __future__ import annotations

"""
File: app/handlers/media_handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Handle admin image messages for SPECIALS.

RULE (LOCKED):
- Admin sends image + caption → SPECIAL
- Stored in specials table (latest wins)
- Immediately pushed to all customers
- Can be replayed later via "SPECIALS"
"""

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models import Contact
from app.outbound.factory import get_meta_client

DEFAULT_CAPTION = "Today’s specials"


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

    # Only handle images
    if msg.get("type") != "image":
        return False

    # Ignore non-admin images silently
    if sender not in admin_allowlist:
        return True

    meta = get_meta_client()

    media_id = msg["image"]["id"]
    caption = msg["image"].get("caption") or DEFAULT_CAPTION

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

    # -------------------------------
    # Push SPECIAL to all customers
    # -------------------------------
    contacts = (
        db.query(Contact)
        .filter(Contact.client_id == client_id)
        .filter(~Contact.contact_number.in_(admin_allowlist))
        .all()
    )

    sent = 0
    failed = 0

    for c in contacts:
        try:
            meta.send_image_message(
                to_msisdn=c.contact_number,
                media_id=media_id,
                caption=caption,
            )
            sent += 1
        except Exception:
            failed += 1

    # -------------------------------
    # Confirm to admin
    # -------------------------------
    meta.send_generic_business_update_template(
        to_msisdn=sender,
        blob_text=f"Special sent to customers. Delivered: {sent}. Failed: {failed}.",
    )

    return True
