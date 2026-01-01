"""
File: app/handlers/admin_commands.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
All Tier-1 admin commands including IMAGE BROADCAST.
"""

import re
from sqlalchemy.orm import Session

from app.models import Client, Contact
from app.outbound.factory import get_meta_client
from app.handlers.media_handler import PENDING_IMAGE, DEFAULT_CAPTION


def _normalise_msisdn(raw: str | None) -> str | None:
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("0"):
        digits = "27" + digits[1:]
    if digits.startswith("27") and len(digits) >= 11:
        return digits
    return None


def handle_admin_command(
    *,
    db: Session,
    sender_number: str,
    message_text: str,
    admin_allowlist: set[str],
) -> bool:

    if sender_number not in admin_allowlist:
        return False

    upper = message_text.strip().upper()
    meta = get_meta_client()
    client = db.query(Client).first()

    if not client:
        return True

    # ---------------- PAUSE / RESUME ----------------
    if upper == "PAUSE":
        client.is_paused = True
        db.commit()
        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text="Outbound messaging is now PAUSED.",
        )
        return True

    if upper == "RESUME":
        client.is_paused = False
        db.commit()
        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text="Outbound messaging has been RESUMED.",
        )
        return True

    # ---------------- COUNT ----------------
    if upper == "COUNT":
        total = db.query(Contact).count()
        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text=f"Active clients: {total}",
        )
        return True

    # ---------------- ADD CLIENT ----------------
    if upper.startswith("ADD CLIENT:"):
        msisdn = _normalise_msisdn(message_text.split(":", 1)[1])
        if not msisdn:
            return True

        contact = db.query(Contact).filter(Contact.contact_number == msisdn).one_or_none()
        if contact:
            msg = f"Client {msisdn} already exists."
        else:
            db.add(Contact(contact_number=msisdn))
            db.commit()
            msg = f"Client {msisdn} added."

        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text=msg,
        )
        return True

    # ---------------- REMOVE CLIENT ----------------
    if upper.startswith("REMOVE CLIENT:"):
        msisdn = _normalise_msisdn(message_text.split(":", 1)[1])
        contact = db.query(Contact).filter(Contact.contact_number == msisdn).one_or_none()

        if contact:
            db.delete(contact)
            db.commit()
            msg = f"Client {msisdn} removed."
        else:
            msg = f"Client {msisdn} not found."

        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text=msg,
        )
        return True

    # ---------------- SEND (single client) ----------------
    if upper.startswith("SEND:"):
        if client.is_paused:
            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text="Outbound is PAUSED. RESUME to continue.",
            )
            return True

        try:
            _, body = message_text.split(":", 1)
            raw, text = body.strip().split(maxsplit=1)
            msisdn = _normalise_msisdn(raw)

            contact = db.query(Contact).filter(Contact.contact_number == msisdn).one_or_none()
            if not contact:
                raise ValueError()

            meta.send_generic_business_update_template(
                to_msisdn=msisdn,
                blob_text=text.strip(),
            )

            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text=f"Message sent to {msisdn}.",
            )
        except Exception:
            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text="SEND failed. Format: SEND: <number> <message>",
            )

        return True

    # ---------------- BROADCAST (TEXT + IMAGE) ----------------
    if upper.startswith("BROADCAST"):
        if client.is_paused:
            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text="Outbound is PAUSED. RESUME to continue.",
            )
            return True

        text = ""
        if ":" in message_text:
            text = message_text.split(":", 1)[1].strip()

        contacts = (
            db.query(Contact)
            .filter(~Contact.contact_number.in_(admin_allowlist))
            .all()
        )

        sent = 0

        for c in contacts:
            # --- IMAGE FIRST ---
            if PENDING_IMAGE["media_id"]:
                meta.send_image(
                    to_msisdn=c.contact_number,
                    media_id=PENDING_IMAGE["media_id"],
                    caption=PENDING_IMAGE["caption"] or DEFAULT_CAPTION,
                )

            # --- TEXT SECOND ---
            if text:
                meta.send_generic_business_update_template(
                    to_msisdn=c.contact_number,
                    blob_text=text,
                )

            sent += 1

        # clear image after broadcast
        PENDING_IMAGE["media_id"] = None
        PENDING_IMAGE["caption"] = None

        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text=f"Broadcast sent to {sent} clients.",
        )
        return True

    return False
