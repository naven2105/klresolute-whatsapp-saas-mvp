"""
WhatsApp webhook endpoint
T-02: Destination number extraction
Still no business logic, no DB writes
"""

from fastapi import APIRouter, Request, Response, status
import logging

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

logger = logging.getLogger("webhooks")
logging.basicConfig(level=logging.INFO)


@router.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    """
    Receives inbound WhatsApp webhook events.

    T-02 responsibilities:
    - Read JSON payload
    - Attempt to extract destination number
    - Log extracted value
    - Always return 200
    """
    try:
        payload = await request.json()
    except Exception:
        logger.warning("Webhook received non-JSON payload")
        return Response(status_code=status.HTTP_200_OK)

    destination_number = None

    # Defensive extraction (Meta payloads are nested)
    try:
        destination_number = (
            payload["entry"][0]["changes"][0]["value"]["metadata"]["display_phone_number"]
        )
    except Exception:
        logger.warning("Destination number not found in payload")

    logger.info("Extracted destination number: %s", destination_number)

    return Response(status_code=status.HTTP_200_OK)
