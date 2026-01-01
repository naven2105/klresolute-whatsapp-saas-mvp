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
    admin_allowlist: set[str],
) -> bool:
    if msg.get("type") != "image":
        return False

    # Ignore images from non-admins
    if sender not in admin_allowlist:
        return True

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
