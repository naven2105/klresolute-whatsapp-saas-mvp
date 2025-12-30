"""
File: app/webhooks.py
Path: app/webhooks.py

Project: KLResolute WhatsApp SaaS MVP

Purpose:
Inbound WhatsApp webhook handler.
Extended to support admin command:
- ADD CLIENT: Name Number
"""

import logging
import os
import re
from fastapi import APIRouter, Request, Response, status, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import (
    WhatsAppNumber,
    Client,
    Contact,
    Conversation,
    Message,
    FaqItem,
)
from app.services.message_service import MessageService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger("webhooks")
logging.basicConfig(level=logging.INFO)


ADMIN_ALLOWLIST = {
    n.strip()
    for n in os.getenv("OUTBOUND_TEST_ALLOWLIST", "").split(",")
    if n.strip()
}


def _normalise_msisdn(raw: str) -> str | None:
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("0"):
        digits = "27" + digits[1:]
    if digits.startswith("27") and len(digits) >= 11:
        return digits
    return None


def _extract_destination_number(payload: dict) -> str | None:
    try:
        return payload["entry"][0]["changes"][0]["value"]["metadata"]["display_phone_number"]
    except Exception:
        return None


def _extract_sender_number(payload: dict) -> str | None:
    try:
        return payload["entry"][0]["changes"][0]["value"]["messages"][0]["from"]
    except Exception:
        return None


def _extract_message_text(payload: dict) -> str | None:
    try:
        return payload["entry"][0]["changes"][0]["value"]["messages"][0]["text"]["body"]
    except Exception:
        return None


@router.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    # ---- T-01 Parse payload ----
    try:
        payload = await request.json()
    except Exception:
        return Response(status_code=status.HTTP_200_OK)

    destination_number = _extract_destination_number(payload)
    sender_number = _extract_sender_number(payload)
    message_text = _extract_message_text(payload)

    if not destination_number or not sender_number or not message_text:
        logger.warning("Required message fields missing")
        return Response(status_code=status.HTTP_200_OK)

    logger.info("Destination number: %s", destination_number)
    logger.info("Sender number: %s", sender_number)
    logger.info("Message text: %s", message_text)

    # ------------------------------------------------------------------
    # ADMIN COMMAND: ADD CLIENT
    # ------------------------------------------------------------------
    if sender_number in ADMIN_ALLOWLIST and message_text.upper().startswith("ADD CLIENT:"):
        try:
            _, body = message_text.split(":", 1)
            parts = body.strip().split()
            if len(parts) < 2:
                logger.warning("ADD CLIENT rejected: invalid format")
                return Response(status_code=status.HTTP_200_OK)

            name = " ".join(parts[:-1])
            msisdn = _normalise_msisdn(parts[-1])

            if not msisdn:
                logger.warning("ADD CLIENT rejected: invalid number")
                return Response(status_code=status.HTTP_200_OK)

            existing = (
                db.query(Contact)
                .filter(Contact.contact_number == msisdn)
                .one_or_none()
            )

            if existing:
                logger.info("ADD CLIENT ignored: contact already exists (%s)", msisdn)
                return Response(status_code=status.HTTP_200_OK)

            contact = Contact(
                contact_number=msisdn,
                opted_in=True,
                source="admin_add",
            )
            db.add(contact)
            db.commit()
            logger.info("ADD CLIENT success: %s %s", name, msisdn)

        except Exception:
            db.rollback()
            logger.exception("ADD CLIENT failed")
        return Response(status_code=status.HTTP_200_OK)

    # ------------------------------------------------------------------
    # Existing pipeline continues unchanged
    # ------------------------------------------------------------------

    wa_number = (
        db.query(WhatsAppNumber)
        .filter(WhatsAppNumber.destination_number == destination_number)
        .one_or_none()
    )
    if not wa_number:
        return Response(status_code=status.HTTP_200_OK)

    client = (
        db.query(Client)
        .filter(Client.client_id == wa_number.client_id)
        .one_or_none()
    )
    if not client:
        return Response(status_code=status.HTTP_200_OK)

    contact = (
        db.query(Contact)
        .filter(Contact.contact_number == sender_number)
        .one_or_none()
    )
    if not contact:
        contact = Contact(
            contact_number=sender_number,
            opted_in=True,
            source="qr",
        )
        db.add(contact)
        db.commit()
        db.refresh(contact)

    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.wa_number_id == wa_number.wa_number_id,
            Conversation.contact_id == contact.contact_id,
            Conversation.closed_at.is_(None),
        )
        .one_or_none()
    )
    if not conversation:
        conversation = Conversation(
            client_id=client.client_id,
            wa_number_id=wa_number.wa_number_id,
            contact_id=contact.contact_id,
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    inbound_msg = Message(
        conversation_id=conversation.conversation_id,
        direction="inbound",
        message_text=message_text,
    )
    db.add(inbound_msg)
    db.commit()

    faqs = (
        db.query(FaqItem)
        .filter(
            FaqItem.client_id == client.client_id,
            FaqItem.is_active.is_(True),
        )
        .all()
    )

    matched_faq = next(
        (f for f in faqs if f.match_pattern.lower() in message_text.lower()),
        None,
    )

    if matched_faq:
        MessageService(db=db).handle_inbound_message(
            inbound_message_id=inbound_msg.message_id,
            conversation_id=conversation.conversation_id,
            inbound_text=message_text,
            selected_response=matched_faq.response_text,
        )

    return Response(status_code=status.HTTP_200_OK)
