"""
File: app/handlers/media_handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Handle admin image messages.

RULE (LOCKED):
- Admin sends an image → image is broadcast IMMEDIATELY
- Optional caption from admin
- If no caption → default caption is used
- No pending state
- No second command
"""

from sqlalchemy.orm import Session

from app.models import Contact, Client
from app.outbound.factory import get_meta_client

DEFAULT_CAPTION = "📸 Today’s update"


def handle_media_message(
    *,
    db: Session,
    sender: str,
    msg: dict,
    admin_allowlist: set[str],
) -> bool:
    """
    Returns True if message was handled (image).
    Returns False if message is NOT an image.
    """

    # Only handle images
    if msg.get("type") != "image":
        return False

    # Ignore images from non-admins (silent)
    if sender not in admin_allowlist:
        return True

    meta = get_meta_client()

    # Extract image + caption
    media_id = msg["image"]["id"]
    caption = msg["image"].get("caption") or DEFAULT_CAPTION

    # Fetch recipients (exclude admins)
    contacts = (
        db.query(Contact)
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
            continue

    # One confirmation to admin
    meta.send_generic_business_update_template(
        to_msisdn=sender,
        blob_text=f"Image broadcast sent. Delivered: {sent}. Failed: {failed}.",
    )

    return True
