"""
File: app/client/commands.py
Path: app/client/commands.py

Purpose:
Client self-service commands.
- STOP   → opt out (remove contact)
- RESUME → opt in (add contact)

Rules:
- Inbound always allowed
- Admin numbers ignored here
"""

from sqlalchemy.orm import Session

from app.models import Contact
from app.outbound.factory import get_meta_client


def handle_client_command(
    *,
    db: Session,
    sender: str,
    msg: dict,
    admin_allowlist: set[str],
) -> bool:
    if msg.get("type") != "text":
        return False

    text = msg["text"]["body"].strip().upper()
    meta = get_meta_client()

    # -------- STOP --------
    if text == "STOP":
        contact = db.query(Contact).filter(Contact.contact_number == sender).one_or_none()
        if contact:
            db.delete(contact)
            db.commit()

        meta.send_generic_business_update_template(
            to_msisdn=sender,
            blob_text="You have been removed. You will no longer receive updates.",
        )
        return True

    # -------- RESUME --------
    if text == "RESUME" and sender not in admin_allowlist:
        existing = db.query(Contact).filter(Contact.contact_number == sender).one_or_none()
        if not existing:
            db.add(Contact(contact_number=sender))
            db.commit()

        meta.send_generic_business_update_template(
            to_msisdn=sender,
            blob_text="You have been added back. You will receive updates again.",
        )
        return True

    return False
