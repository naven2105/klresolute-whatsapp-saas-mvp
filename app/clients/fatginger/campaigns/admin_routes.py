from __future__ import annotations

"""
File: app/clients/fatginger/campaigns/admin_routes.py
Path: app/clients/fatginger/campaigns/admin_routes.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
FatGinger Campaign Admin API

Sprint 5:
- Create campaign (DRAFT)
- Manual trigger send
- List campaigns
- View campaign logs
- Tenant locked to r_fg__
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db import get_db
from app.clients.fatginger.campaigns.service import (
    create_campaign,
    trigger_campaign_send,
)

# ✅ FIX: auth module path (was app.auth.* which doesn't exist)
from app.admin.auth import require_admin_user

from app.messaging.client_messenger import (
    send_text_message,
    send_image_message,
)

logger = logging.getLogger(__name__)

TENANT_PREFIX = "r_fg__"
T_CAMPAIGNS = f"{TENANT_PREFIX}campaigns"
T_LOGS = f"{TENANT_PREFIX}broadcast_logs"

router = APIRouter(
    prefix="/admin/fatginger/campaigns",
    tags=["FatGinger Campaign Admin"],
)


class CampaignCreateRequest(BaseModel):
    title: str
    message: str
    image_url: Optional[str] = None


@router.post("/create")
def create_campaign_endpoint(
    payload: CampaignCreateRequest,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin_user),
):
    try:
        campaign = create_campaign(
            db=db,
            title=payload.title,
            message=payload.message,
            image_url=payload.image_url,
        )
        return {"status": "CREATED", "campaign_id": campaign.id}
    except Exception as ex:
        logger.exception("ADMIN_CAMPAIGN_CREATE_ERROR | tenant=r_fg__")
        raise HTTPException(status_code=500, detail=str(ex))


@router.get("/list")
def list_campaigns(
    db: Session = Depends(get_db),
    _admin=Depends(require_admin_user),
):
    rows = db.execute(
        text(
            f"""
            SELECT
                c.id,
                c.title,
                c.status,
                c.created_at,
                COUNT(l.id) AS total_logs
            FROM {T_CAMPAIGNS} c
            LEFT JOIN {T_LOGS} l
              ON l.campaign_id = c.id
            GROUP BY c.id
            ORDER BY c.created_at DESC
            """
        )
    ).mappings().all()

    return {"campaigns": rows}


@router.get("/{campaign_id}/logs")
def view_campaign_logs(
    campaign_id: str,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin_user),
):
    rows = db.execute(
        text(
            f"""
            SELECT
                customer_phone,
                delivery_status,
                sent_at
            FROM {T_LOGS}
            WHERE campaign_id = :campaign_id
            ORDER BY sent_at DESC
            """
        ),
        {"campaign_id": campaign_id},
    ).mappings().all()

    return {"logs": rows}


@router.post("/{campaign_id}/send")
def manual_send_campaign(
    campaign_id: str,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin_user),
):
    try:
        result = trigger_campaign_send(
            db=db,
            campaign_id=campaign_id,
            send_text=send_text_message,
            send_image=send_image_message,
        )
        return result
    except Exception as ex:
        logger.exception(
            "ADMIN_CAMPAIGN_SEND_ERROR | tenant=r_fg__ | campaign_id=%s",
            campaign_id,
        )
        raise HTTPException(status_code=500, detail=str(ex))