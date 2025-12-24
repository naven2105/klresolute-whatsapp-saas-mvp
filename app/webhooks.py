"""
WhatsApp webhook endpoint
Skeleton only – no business logic
"""

from fastapi import APIRouter, Request, Response, status

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    """
    Receives inbound WhatsApp webhook events.
    MVP skeleton:
    - Accept request
    - Do not parse payload
    - Always return 200
    """
    # Intentionally ignore body for now
    return Response(status_code=status.HTTP_200_OK)
