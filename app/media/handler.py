from __future__ import annotations

"""
File: app/media/handler.py
Path: app/media/handler.py

Purpose:
Admin image intake (MVP).
- Accept ONE image from admin
- Store media_id in memory
- Optional caption
- Used on next BROADCAST only
"""

from app.outbound.factory import get_meta_client
from app.utils.admin import is_admin_message

DEFAULT_CAPTION = "📸 Today’s update"

PENDING_IMAGE = {
    "media_id": None,
    "caption": None,
}


def handle_media_message(
    *,
    db,
    sender: str,
    msg: dict,
    business_msisdn: str,
) -> bool:
    """
    Returns True if message was handled.
    Returns False if message is NOT an image.
    """

    if msg.get("type") != "image":
        return False

    # ----------------------------------
    # Admin-only (DB-driven, fail-closed)
    # ----------------------------------
    if not is_admin_message(
        db=db,
        sender=sender,
        business_msisdn=business_msisdn,
    ):
        return True  # explicitly consumed, ignored

    media_id = msg["image"]["id"]
    caption = msg["image"].get("caption") or DEFAULT_CAPTION

    PENDING_IMAGE["media_id"] = media_id
    PENDING_IMAGE["caption"] = caption

    meta = get_meta_client()
    meta.send_generic_business_update_template(
        to_msisdn=sender,
        blob_text="Image received. It will be included in the next BROADCAST.",
    )

    return True
