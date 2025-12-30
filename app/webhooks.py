"""
File: app/webhooks.py
Path: app/webhooks.py

Project: KLResolute WhatsApp SaaS MVP

Purpose:
Inbound WhatsApp webhook handler responsible for message ingestion and state resolution.
Implements the sequential pipeline defined in the BRS.

Processing order (STRICT — do not reorder):
T-01 Webhook ingress
T-02 Destination number extraction
T-03 Client resolution
T-04 Contact resolution
T-05 Conversation resolution
T-06 Message persistence (immutable)
T-07 FAQ matching (read-only)
T-08 Response selection (authoritative handoff)

Critical design rules:
- Logic is strictly sequential; later stages depend on earlier resolution
- No outbound messages are sent from this module
- Failures degrade gracefully and always return HTTP 200
- Outbound message creation is delegated to MessageService (authoritative)
"""

import logging
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


# -------------------------------------------------
# Extraction helpers
# -------------------------------------------------
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


# -------------------------------------------------
# Webhook endpoint
# -------------------------------------------------
@router.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    # ---- T-01: Parse payload ----
    try:
        payload = await request.json()
    except Exception:
        logger.warning("Webhook received non-JSON payload")
        return Response(status_code=status.HTTP_200_OK)

    # ---- T-02: Extract routing + content ----
    destination_number = _extract_destination_number(payload)
    sender_number = _extract_sender_number(payload)
    message_text = _extract_message_text(payload)

    if not destination_number or not sender_number or not message_text:
        logger.warning("Required message fields missing")
        return Response(status_code=status.HTTP_200_OK)

    logger.info("Destination number: %s", destination_number)
    logger.info("Sender number: %s", sender_number)
    logger.info("Message text: %s", message_text)

    # ---- T-03: Client resolution ----
    wa_number = (
        db.query(WhatsAppNumber)
        .filter(WhatsAppNumber.destination_number == destination_number)
        .one_or_none()
    )
    if not wa_number:
        logger.warning("No WhatsApp number registered for %s", destination_number)
        return Response(status_code=status.HTTP_200_OK)

    client = (
        db.query(Client)
        .filter(Client.client_id == wa_number.client_id)
        .one_or_none()
    )
    if not client:
        logger.error("Client missing for WhatsApp number")
        return Response(status_code=status.HTTP_200_OK)

    # ---- T-04: Contact resolution ----
    try:
        contact = (
            db.query(Contact)
            .filter(Contact.contact_number == sender_number)
            .one_or_none()
        )
        if not contact:
            contact = Contact(contact_number=sender_number)
            db.add(contact)
            db.commit()
            db.refresh(contact)
            logger.info("Created contact: %s", contact.contact_id)
    except Exception:
        db.rollback()
        return Response(status_code=status.HTTP_200_OK)

    # ---- T-05: Conversation resolution ----
    try:
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
            logger.info("Created conversation: %s", conversation.conversation_id)
    except Exception:
        db.rollback()
        return Response(status_code=status.HTTP_200_OK)

    # ---- T-06: Persist inbound message ----
    try:
        inbound_msg = Message(
            conversation_id=conversation.conversation_id,
            direction="inbound",
            message_text=message_text,
        )
        db.add(inbound_msg)
        db.commit()
        db.refresh(inbound_msg)
    except Exception:
        db.rollback()
        return Response(status_code=status.HTTP_200_OK)

    # ---- T-23: Handover silence ----
    if conversation.status == "handed_over":
        return Response(status_code=status.HTTP_200_OK)

    # ---- T-07: FAQ matching ----
    faqs = (
        db.query(FaqItem)
        .filter(
            FaqItem.client_id == client.client_id,
            FaqItem.is_active.is_(True),
        )
        .all()
    )

    matched_faq = None
    text_lower = message_text.lower()
    for faq in faqs:
        if faq.match_pattern.lower() in text_lower:
            matched_faq = faq
            break

    # ---- T-08: Response selection (MVP) ----
    if matched_faq:
        selected_response = matched_faq.response_text
        logger.info("FAQ matched: %s", matched_faq.faq_name)
    else:
        # MVP DEFAULT RESPONSE (critical)
        selected_response = (
            "👋 Welcome!\n"
            "Today’s update is available.\n"
            "Reply HOURS, LOCATION or SPECIALS."
        )
        logger.info("No FAQ match — default welcome response selected")

    # ---- Delegate outbound creation ----
    try:
        MessageService(db=db).handle_inbound_message(
            inbound_message_id=inbound_msg.message_id,
            conversation_id=conversation.conversation_id,
            inbound_text=message_text,
            selected_response=selected_response,
        )
    except Exception:
        db.rollback()
        return Response(status_code=status.HTTP_200_OK)

    return Response(status_code=status.HTTP_200_OK)
