"""
File: app/handlers/client_commands.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Handle client self-service commands only.

Supported commands:
- STOP    → remove client from contacts (opt-out)
- RESUME  → add client back to contacts (opt-in)

Rules:
- Contacts table is the source of truth
- Deleting a contact = opted out
- No admin logic here
"""

from sqlalchemy.orm import Session

from app.models import Contact
from app.outbound.factory import get_meta_client


def handle_client_command(
    *,
    db: Session,
    sender_number: str,
    message_text: str,
) -> bool:
    """
    Returns True if a client command was handled.
    Returns False if message is NOT a client command.
    """

    upper = message_text.strip().upper()
    meta = get_meta_client()

    # ---------------------------
    # STOP → opt out
    # ---------------------------
    if upper == "STOP":
        contact = (
            db.query(Contact)
            .filter(Contact.contact_number == sender_number)
            .one_or_none()
        )

        if contact:
            db.delete(contact)
            db.commit()

        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text="You have been removed and will no longer receive updates.",
        )
        return True

    # ---------------------------
    # RESUME → opt in
    # ---------------------------
    if upper == "RESUME":
        contact = (
            db.query(Contact)
            .filter(Contact.contact_number == sender_number)
            .one_or_none()
        )

        if not contact:
            db.add(Contact(contact_number=sender_number))
            db.commit()

        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text="You have been added back and will receive updates again.",
        )   
        return True

    return False
