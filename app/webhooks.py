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
- COUNT
- PAUSE
- RESUME

Client commands:
- STOP
- RESUME

Standards:
- NO deletes
- Opt-out affects outbound only
- PAUSE affects all outbound
"""

import logging
import os
import re

from fastapi import APIRouter, Request, Response, status, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import WhatsAppNumber, Client, Contact
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
            value["metadata"]["display_phone_number"],
            value["messages"][0]["from"],
            value["messages"][0]["text"]["body"],
        )
    except Exception:
        return None, None, None


@router.post("/whatsapp")
async def whatsapp_webhook(request: Request, db: Session = Depends(get_db)):
    try:
        payload = await request.json()
    except Exception:
        return Response(status_code=status.HTTP_200_OK)

    destination_number, sender_number, message_text = _extract(payload)

    if not destination_number or not sender_number or not message_text:
        logger.warning("Required message fields missing")
        return Response(status_code=status.HTTP_200_OK)

    # ---- NORMALISE SENDER (CRITICAL FIX) ----
    sender_number = _normalise_msisdn(sender_number)

    upper = message_text.upper().strip()
    meta = get_meta_client()

    # ==========================================================
    # CLIENT SELF-SERVICE
    # ==========================================================
    contact = db.query(Contact).filter(Contact.contact_number == sender_number).one_or_none()

    if upper == "STOP":
        if contact:
            contact.is_opted_out = True
            db.commit()

        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text="You have been opted out. You will no longer receive updates.",
        )
        return Response(status_code=status.HTTP_200_OK)

    if upper == "RESUME" and sender_number not in ADMIN_ALLOWLIST:
        if not contact:
            contact = Contact(contact_number=sender_number, is_opted_out=False)
            db.add(contact)
        else:
            contact.is_opted_out = False

        db.commit()

        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text="You have been opted back in. You will receive updates again.",
        )
        return Response(status_code=status.HTTP_200_OK)

    # ==========================================================
    # ADMIN COMMANDS
    # ==========================================================
    if sender_number in ADMIN_ALLOWLIST:

        client = db.query(Client).first()
        if not client:
            return Response(status_code=status.HTTP_200_OK)

        # -------- PAUSE --------
        if upper == "PAUSE":
            client.is_paused = True
            db.commit()

            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text="Outbound messaging is now PAUSED.",
            )
            return Response(status_code=status.HTTP_200_OK)

        # -------- RESUME --------
        if upper == "RESUME":
            client.is_paused = False
            db.commit()

            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text="Outbound messaging has been RESUMED.",
            )
            return Response(status_code=status.HTTP_200_OK)

        # -------- COUNT --------
        if upper == "COUNT":
            active = db.query(Contact).filter(Contact.is_opted_out.is_(False)).count()
            opted_out = db.query(Contact).filter(Contact.is_opted_out.is_(True)).count()

            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text=f"Client summary:\nActive: {active}\nOpted out: {opted_out}",
            )
            return Response(status_code=status.HTTP_200_OK)

        # -------- ADD CLIENT --------
        if upper.startswith("ADD CLIENT:"):
            msisdn = _normalise_msisdn(message_text.split(":", 1)[1])
            if not msisdn:
                return Response(status_code=status.HTTP_200_OK)

            contact = db.query(Contact).filter(Contact.contact_number == msisdn).one_or_none()
            if contact:
                contact.is_opted_out = False
                msg = f"Client {msisdn} re-enabled."
            else:
                db.add(Contact(contact_number=msisdn, is_opted_out=False))
                msg = f"Client {msisdn} added."

            db.commit()

            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text=msg,
            )
            return Response(status_code=status.HTTP_200_OK)

        # -------- REMOVE CLIENT --------
        if upper.startswith("REMOVE CLIENT:"):
            msisdn = _normalise_msisdn(message_text.split(":", 1)[1])
            if not msisdn:
                return Response(status_code=status.HTTP_200_OK)

            contact = db.query(Contact).filter(Contact.contact_number == msisdn).one_or_none()
            if contact:
                contact.is_opted_out = True
                db.commit()
                msg = f"Client {msisdn} opted out."
            else:
                msg = f"Client {msisdn} not found."

            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text=msg,
            )
            return Response(status_code=status.HTTP_200_OK)

        # -------- SEND --------
        if upper.startswith("SEND:"):
            if client.is_paused:
                meta.send_generic_business_update_template(
                    to_msisdn=sender_number,
                    blob_text="Outbound is PAUSED. RESUME to continue.",
                )
                return Response(status_code=status.HTTP_200_OK)

            try:
                _, body = message_text.split(":", 1)
                raw, text = body.strip().split(maxsplit=1)
                msisdn = _normalise_msisdn(raw)

                contact = db.query(Contact).filter(Contact.contact_number == msisdn).one_or_none()
                if not contact or contact.is_opted_out:
                    raise ValueError("Client opted out")

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

            return Response(status_code=status.HTTP_200_OK)  

    # ==========================================================
    # MVP: ignore everything else
    # ==========================================================
    return Response(status_code=status.HTTP_200_OK)
