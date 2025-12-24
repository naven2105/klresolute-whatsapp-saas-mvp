"""
WhatsApp webhook endpoint
T-03: Client resolution (DB read only)
"""

from fastapi import APIRouter, Request, Response, status, Depends
import logging
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import WhatsAppNumber, Client

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

logger = logging.getLogger("webhooks")
logging.basicConfig(level=logging.INFO)


@router.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    T-03 responsibilities:
    - Read JSON payload
    - Extract destination number
    - Resolve WhatsAppNumber
    - Resolve Client
    - Log result
    - Always return 200
    """
    try:
        payload = await request.json()
    except Exception:
        logger.warning("Webhook received non-JSON payload")
        return Response(status_code=status.HTTP_200_OK)

    destination_number = None

    try:
        destination_number = (
            payload["entry"][0]["changes"][0]["value"]["metadata"]["display_phone_number"]
        )
    except Exception:
        logger.warning("Destination number not found in payload")
        return Response(status_code=status.HTTP_200_OK)

    logger.info("Destination number: %s", destination_number)

    # ---- DB READ ONLY BELOW ----

    try:
        wa_number = (
            db.query(WhatsAppNumber)
            .filter(WhatsAppNumber.destination_number == destination_number)
            .one_or_none()
        )
    except Exception as e:
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

    logger.info(
        "Resolved client: id=%s name=%s",
        client.client_id,
        client.client_name,
    )

    return Response(status_code=status.HTTP_200_OK)
