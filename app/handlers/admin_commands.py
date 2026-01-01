"""
File: app/handlers/admin_commands.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
All Tier-1 admin commands.

Supported commands:
- ADD CLIENT: <number>
- REMOVE CLIENT: <number>
- SEND: <number> <message>
- BROADCAST: <message>
- COUNT
- PAUSE
- RESUME

Rules:
- Contacts table is source of truth
- Contact exists = opted in
- No schema changes
- Admin numbers never receive BROADCAST
- MVP: PAUSE/RESUME acknowledged only (no DB flag)
"""

from __future__ import annotations

import re
from sqlalchemy.orm import Session

from app.models import Contact
from app.outbound.factory import get_meta_client


def _normalise_msisdn(raw: str | None) -> str | None:
    digits = re.sub(r"\D", "", raw or "")
    if not digits:
        return None
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
    """
    Returns True if an admin command was handled.
    Returns False if message is NOT an admin command.
    """
    if sender_number not in admin_allowlist:
        return False

    text = (message_text or "").strip()
    upper = text.upper()

    meta = get_meta_client()

    # ---------------------------
    # PAUSE / RESUME (MVP: no DB flag)
    # ---------------------------
    if upper == "PAUSE":
        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text="PAUSE noted. (MVP: pause flag not enabled yet.)",
        )
        return True

    if upper == "RESUME":
        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text="RESUME noted. (MVP: pause flag not enabled yet.)",
        )
        return True

    # ---------------------------
    # COUNT
    # ---------------------------
    if upper == "COUNT":
        total = db.query(Contact).count()
        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text=f"Active clients: {total}",
        )
        return True

    # ---------------------------
    # ADD CLIENT
    # ---------------------------
    if upper.startswith("ADD CLIENT:"):
        msisdn = _normalise_msisdn(text.split(":", 1)[1] if ":" in text else None)
        if not msisdn:
            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text="ADD CLIENT failed. Format: ADD CLIENT: <number>",
            )
            return True

        existing = db.query(Contact).filter(Contact.contact_number == msisdn).one_or_none()
        if existing:
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

    # ---------------------------
    # REMOVE CLIENT
    # ---------------------------
    if upper.startswith("REMOVE CLIENT:"):
        msisdn = _normalise_msisdn(text.split(":", 1)[1] if ":" in text else None)
        if not msisdn:
            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text="REMOVE CLIENT failed. Format: REMOVE CLIENT: <number>",
            )
            return True

        existing = db.query(Contact).filter(Contact.contact_number == msisdn).one_or_none()
        if existing:
            db.delete(existing)
            db.commit()
            msg = f"Client {msisdn} removed."
        else:
            msg = f"Client {msisdn} not found."

        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text=msg,
        )
        return True

    # ---------------------------
    # SEND
    # ---------------------------
    if upper.startswith("SEND:"):
        try:
            _, body = text.split(":", 1)
            raw, msg_text = body.strip().split(maxsplit=1)
            msisdn = _normalise_msisdn(raw)
            if not msisdn or not msg_text.strip():
                raise ValueError()

            existing = db.query(Contact).filter(Contact.contact_number == msisdn).one_or_none()
            if not existing:
                meta.send_generic_business_update_template(
                    to_msisdn=sender_number,
                    blob_text=f"Message NOT sent. Client {msisdn} not in list.",
                )
                return True

            meta.send_generic_business_update_template(
                to_msisdn=msisdn,
                blob_text=msg_text.strip(),
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

    # ---------------------------
    # BROADCAST
    # ---------------------------
    if upper.startswith("BROADCAST:"):
        broadcast_text = text.split(":", 1)[1].strip() if ":" in text else ""
        if not broadcast_text:
            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text="BROADCAST failed. Format: BROADCAST: <message>",
            )
            return True

        contacts = (
            db.query(Contact)
            .filter(~Contact.contact_number.in_(admin_allowlist))
            .all()
        )

        sent = 0
        failed = 0
        for c in contacts:
            try:
                meta.send_generic_business_update_template(
                    to_msisdn=c.contact_number,
                    blob_text=broadcast_text,
                )
                sent += 1
            except Exception:
                failed += 1

        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text=f"Broadcast complete. Sent: {sent}. Failed: {failed}.",
        )
        return True

    return False
