"""
WhatsApp webhook endpoint
T-06: Message persistence (immutable)
"""

from fastapi import APIRouter, Request, Response, status, Depends
import logging
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import (
    WhatsAppNumber,
    Client,
    Contact,
    Conversation,
    Message,
)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

logger = logging.getLogger("webhooks")
logging.basicConfig(level=logging.INFO)


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
    """
    T-06 responsibilities:
    - Resolve client
    - Resolve contact
    - Resolve conversation
    - Persist inbound message (immutable)
    - Always return 200
    """
    try:
        payload = await request.json()
    except Exception:
        logger.warning("Webhook received non-JSON payload")
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

    # ---- Client resolution ----
    try:
        wa_number = (
            db.query(WhatsAppNumber)
            .filter(WhatsAppNumber.destination_number == destination_number)
            .one_or_none()
        )
    except Exception:
        logger.warning("Database unavailable during client resolution")
        return Response(status_code=status.HTTP_200_OK)

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

    # ---- Contact resolution ----
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
        else:
            logger.info("Found contact: %s", contact.contact_id)

    except Exception:
        db.rollback()
        logger.warning("Database unavailable during contact resolution")
        return Response(status_code=status.HTTP_200_OK)

    # ---- Conversation resolution ----
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
        else:
            logger.info("Reused conversation: %s", conversation.conversation_id)

    except Exception:
        db.rollback()
        logger.warning("Database unavailable during conversation resolution")
        return Response(status_code=status.HTTP_200_OK)

    # ---- Message persistence (immutable) ----
    try:
        message = Message(
            conversation_id=conversation.conversation_id,
            direction="inbound",
            message_text=message_text,
        )
        db.add(message)
        db.commit()
        logger.info("Stored inbound message")

    except Exception:
        db.rollback()
        logger.warning("Database unavailable during message persistence")
        return Response(status_code=status.HTTP_200_OK)

    return Response(status_code=status.HTTP_200_OK)
