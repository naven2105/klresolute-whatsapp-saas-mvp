"""
File: app/webhooks.py
Path: app/webhooks.py

Project: KLResolute WhatsApp SaaS MVP

Purpose:
Inbound WhatsApp webhook handler.

Admin commands (Tier 1 – LOCKED):
- ADD CLIENT: <number>
- REMOVE CLIENT: <number>
- SEND: <number> <message>
- BROADCAST: <message>
- COUNT
- PAUSE
- RESUME

Client commands:
- STOP    (remove contact)
- RESUME  (add contact)

Standards:
- Contacts table is source of truth
- Contact exists = opted in
- No schema changes required
- PAUSE blocks all outbound (SEND + BROADCAST)
- Admin numbers never receive BROADCAST
"""

import logging
import os
import re

from fastapi import APIRouter, Request, Response, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Client, Contact
from app.outbound.factory import get_meta_client

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger("webhooks")
logging.basicConfig(level=logging.INFO)

ADMIN_ALLOWLIST = {
    n.strip()
    for n in os.getenv("OUTBOUND_TEST_ALLOWLIST", "").split(",")
    if n.strip()
}


def _normalise_msisdn(raw: str | None) -> str | None:
    digits = re.sub(r"\D", "", raw or "")
    if not digits:
        return None
    if digits.startswith("0"):
        digits = "27" + digits[1:]
    if digits.startswith("27") and len(digits) >= 11:
        return digits
    return None


def _extract(payload: dict):
    try:
        value = payload["entry"][0]["changes"][0]["value"]
        return (
            value["messages"][0]["from"],
            value["messages"][0]["text"]["body"],
        )
    except Exception:
        return None, None


@router.post("/whatsapp")
async def whatsapp_webhook(request: Request, db: Session = Depends(get_db)):
    try:
        payload = await request.json()
    except Exception:
        return Response(status_code=200)

    sender_number, message_text = _extract(payload)
    sender_number = _normalise_msisdn(sender_number)

    if not sender_number or not message_text:
        return Response(status_code=200)

    upper = message_text.upper().strip()
    meta = get_meta_client()

    # ==================================================
    # CLIENT SELF-SERVICE
    # ==================================================
    if upper == "STOP":
        contact = db.query(Contact).filter(Contact.contact_number == sender_number).one_or_none()
        if contact:
            db.delete(contact)
            db.commit()

        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text="You have been removed. You will no longer receive updates.",
        )
        return Response(status_code=200)

    if upper == "RESUME" and sender_number not in ADMIN_ALLOWLIST:
        existing = db.query(Contact).filter(Contact.contact_number == sender_number).one_or_none()
        if not existing:
            db.add(Contact(contact_number=sender_number))
            db.commit()

        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text="You have been added back. You will receive updates again.",
        )
        return Response(status_code=200)

    # ==================================================
    # ADMIN COMMANDS
    # ==================================================
    if sender_number in ADMIN_ALLOWLIST:
        client = db.query(Client).first()
        if not client:
            return Response(status_code=200)

        # -------- PAUSE --------
        if upper == "PAUSE":
            client.is_paused = True
            db.commit()
            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text="Outbound messaging is now PAUSED.",
            )
            return Response(status_code=200)

        # -------- RESUME --------
        if upper == "RESUME":
            client.is_paused = False
            db.commit()
            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text="Outbound messaging has been RESUMED.",
            )
            return Response(status_code=200)

        # -------- COUNT --------
        if upper == "COUNT":
            total = db.query(Contact).count()
            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text=f"Active clients: {total}",
            )
            return Response(status_code=200)

        # -------- ADD CLIENT --------
        if upper.startswith("ADD CLIENT:"):
            msisdn = _normalise_msisdn(message_text.split(":", 1)[1])
            if msisdn:
                exists = db.query(Contact).filter(Contact.contact_number == msisdn).one_or_none()
                if not exists:
                    db.add(Contact(contact_number=msisdn))
                    db.commit()
                    msg = f"Client {msisdn} added."
                else:
                    msg = f"Client {msisdn} already exists."

                meta.send_generic_business_update_template(
                    to_msisdn=sender_number,
                    blob_text=msg,
                )
            return Response(status_code=200)

        # -------- REMOVE CLIENT --------
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
            return Response(status_code=200)

        # -------- SEND --------
        if upper.startswith("SEND:"):
            if client.is_paused:
                meta.send_generic_business_update_template(
                    to_msisdn=sender_number,
                    blob_text="Outbound is PAUSED. RESUME to continue.",
                )
                return Response(status_code=200)

            try:
                _, body = message_text.split(":", 1)
                raw, text = body.strip().split(maxsplit=1)
                msisdn = _normalise_msisdn(raw)

                contact = db.query(Contact).filter(Contact.contact_number == msisdn).one_or_none()
                if not contact:
                    raise ValueError()

                meta.send_generic_business_update_template(
                    to_msisdn=msisdn,
                    blob_text=text,
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

            return Response(status_code=200)

        # -------- BROADCAST --------
        if upper.startswith("BROADCAST:"):
            if client.is_paused:
                meta.send_generic_business_update_template(
                    to_msisdn=sender_number,
                    blob_text="Outbound is PAUSED. RESUME to continue.",
                )
                return Response(status_code=200)

            broadcast_text = message_text.split(":", 1)[1].strip()
            if not broadcast_text:
                meta.send_generic_business_update_template(
                    to_msisdn=sender_number,
                    blob_text="BROADCAST failed. Format: BROADCAST: <message>",
                )
                return Response(status_code=200)

            recipients = (
                db.query(Contact)
                .filter(~Contact.contact_number.in_(list(ADMIN_ALLOWLIST)))
                .all()
            )

            if not recipients:
                meta.send_generic_business_update_template(
                    to_msisdn=sender_number,
                    blob_text="Broadcast not sent. No active clients.",
                )
                return Response(status_code=200)

            sent = 0
            failed = 0

            for c in recipients:
                try:
                    meta.send_generic_business_update_template(
                        to_msisdn=c.contact_number,
                        blob_text=broadcast_text,
                    )
                    sent += 1
                except Exception:
                    failed += 1
                    continue

            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text=f"Broadcast complete. Sent: {sent}. Failed: {failed}.",
            )
            logger.info("BROADCAST by %s sent=%s failed=%s", sender_number, sent, failed)
            return Response(status_code=200)

        # Unknown admin command → ignore
        return Response(status_code=200)

    # Non-admin, non-client-command → ignore
    return Response(status_code=200)
