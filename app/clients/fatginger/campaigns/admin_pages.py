from __future__ import annotations

"""
File: app/clients/fatginger/campaigns/admin_pages.py
Path: app/clients/fatginger/campaigns/admin_pages.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Server-rendered HTML admin pages for FatGinger Campaigns.

Rules:
- Tenant locked to r_fg__
- No cross-tenant sending
- Uses service layer for create + send
- Reads logs directly
"""

import logging
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db import get_db

# ✅ FIX: avoid circular import (do NOT import templates from app.main)
templates = Jinja2Templates(directory="templates")

# ✅ FIX: auth module path (was app.auth.* which doesn't exist)
from app.admin.auth import require_admin_user

from app.clients.fatginger.campaigns.service import (
    create_campaign,
    trigger_campaign_send,
)
from app.messaging.client_messenger import (
    send_text_message,
    send_image_message,
)

logger = logging.getLogger(__name__)

TENANT_PREFIX = "r_fg__"
T_CAMPAIGNS = f"{TENANT_PREFIX}campaigns"
T_LOGS = f"{TENANT_PREFIX}broadcast_logs"

router = APIRouter(prefix="/admin/fatginger/ui", tags=["FatGinger Campaign UI"])


@router.get("/campaigns")
def campaign_list(
    request: Request,
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

    return templates.TemplateResponse(
        "campaign_list.html",
        {"request": request, "campaigns": rows},
    )


@router.get("/campaigns/create")
def campaign_create_form(
    request: Request,
    _admin=Depends(require_admin_user),
):
    return templates.TemplateResponse(
        "campaign_create.html",
        {"request": request},
    )


@router.post("/campaigns/create")
def campaign_create_submit(
    request: Request,
    title: str = Form(...),
    message: str = Form(...),
    image_url: str = Form(""),
    db: Session = Depends(get_db),
    _admin=Depends(require_admin_user),
):
    create_campaign(
        db=db,
        title=title,
        message=message,
        image_url=image_url or None,
    )

    return RedirectResponse(
        url="/admin/fatginger/ui/campaigns",
        status_code=303,
    )


@router.post("/campaigns/{campaign_id}/send")
def campaign_send(
    campaign_id: str,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin_user),
):
    trigger_campaign_send(
        db=db,
        campaign_id=campaign_id,
        send_text=send_text_message,
        send_image=send_image_message,
    )

    return RedirectResponse(
        url="/admin/fatginger/ui/campaigns",
        status_code=303,
    )


@router.get("/campaigns/{campaign_id}/logs")
def campaign_logs(
    campaign_id: str,
    request: Request,
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

    return templates.TemplateResponse(
        "campaign_logs.html",
        {"request": request, "logs": rows},
    )