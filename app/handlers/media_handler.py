"""
File: app/handlers/media_handler.py

Purpose:
Admin image intake (single image MVP).
"""

from app.outbound.factory import get_meta_client

PENDING_IMAGE = {
    "media_id": None,
    "caption": None,
}

DEFAULT_CAPTION = "📸 Today’s update"


def handle_media_message(*, db, sender: str, msg: dict, admin_allowlist: set[str]) -> bool:
    if msg.get("type") != "image":
        return False

    if sender not in admin_allowlist:
        return True  # ignore silently

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
