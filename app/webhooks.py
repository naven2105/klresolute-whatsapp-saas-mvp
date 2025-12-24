"""
WhatsApp webhook endpoint
T-04: Contact resolution (conditional create)
"""

from fastapi import APIRouter, Request, Response, status, Depends
import logging
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import WhatsAppNumber, Client, Contact

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

logger = logging.getLogger("webhooks")
logging.basicConfig(level=logging.INFO)


def _extract_destination_number(payload: dict) -> str | None:
    try:
        return payload["entry"][0]["changes"][0]["value"]["metadata"]["display_phone_number"]
    except Exception:
        return None


def _extract_sender_number(payload: dict) -> str | None:
    """
    Meta inbound message payloads typically include the sender in:
    entry[0].changes[0].value.messages[0].from
    """
    try:
        return payload["entry"][0]["changes"][0]["value"]["messages"][0]["from"]
    except Exception:
        return None


@router.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    T-04 responsibilities:
    - Read JSON payload
    - Extract destination number
    - Extract sender number
    - Resolve/create Contact (DB write allowed)
    - Log what happened
    - Always return 200
    """
    try:
        payload = await request.json()
    except Exception:
        logger.warning("Webhook received non-JSON payload")
        return Response(status_code=status.HTTP_200_OK)

    destination_number = _extract_destination_number(payload)
    if not destination_number:
        logger.warning("Destination number not found in payload")
        return Response(status_code=status.HTTP_200_OK)

    sender_number = _extract_sender_number(payload)
    if not sender_number:
        logger.warning("Sender number not found in payload")
        return Response(status_code=status.HTTP_200_OK)

    logger.info("Destination number: %s", destination_number)
    logger.info("Sender number: %s", sender_number)

    # --- DB: resolve client number mapping (read-only) ---
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
        logger.error("WhatsApp number exists but client missing (data error)")
        return Response(status_code=status.HTTP_200_OK)

    logger.info("Resolved client: id=%s name=%s", client.client_id, client.client_name)

    # --- DB: resolve/create contact (write allowed) ---
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
            logger.info("Created new contact: contact_id=%s", contact.contact_id)
        else:
            logger.info("Found existing contact: contact_id=%s", contact.contact_id)

    except Exception:
        db.rollback()
        logger.warning("Database unavailable during contact resolution")
        return Response(status_code=status.HTTP_200_OK)

    return Response(status_code=status.HTTP_200_OK)
