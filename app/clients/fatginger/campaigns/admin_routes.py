from __future__ import annotations

"""
File: app/clients/fatginger/campaigns/admin_routes.py
Path: app/clients/fatginger/campaigns/admin_routes.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Admin-only manual trigger endpoint for FatGinger campaigns.

Sprint 5 Rules:
- Tenant locked to r_fg__
- No cross-tenant sending
- No dispatcher modification
- Manual trigger only
- STOP users excluded via service layer
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.clients.fatginger.campaigns.service import (
    trigger_campaign_send,
)

# IMPORTANT:
# Use your existing admin auth dependency here
# Replace with your real dependency if different
from app.auth.admin_auth import require_admin_user  # adjust if needed

from app.messaging.client_messenger import (
    send_text_message,
    send_image_message,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin/fatginger/campaigns",
    tags=["FatGinger Campaign Admin"],
)


@router.post("/{campaign_id}/send")
def manual_send_campaign(
    campaign_id: str,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin_user),
):
    """
    Manual trigger endpoint.

    POST /admin/fatginger/campaigns/{campaign_id}/send
    """

    logger.info(
        "ADMIN_CAMPAIGN_SEND_REQUEST | tenant=r_fg__ | campaign_id=%s",
        campaign_id,
    )

    try:
        result = trigger_campaign_send(
            db=db,
            campaign_id=campaign_id,
            send_text=send_text_message,
            send_image=send_image_message,
        )

        return {
            "status": "OK",
            "campaign_id": result["campaign_id"],
            "total": result["total"],
            "sent": result["sent"],
            "failed": result["failed"],
        }

    except Exception as ex:
        logger.exception(
            "ADMIN_CAMPAIGN_SEND_ERROR | tenant=r_fg__ | campaign_id=%s",
            campaign_id,
        )
        raise HTTPException(status_code=500, detail=str(ex))