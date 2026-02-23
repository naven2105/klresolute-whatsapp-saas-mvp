from __future__ import annotations

"""
File: app/clients/fatginger/campaigns/admin_pages.py
Path: app/clients/fatginger/campaigns/admin_pages.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Server-rendered HTML admin pages for FatGinger Campaigns.

Sprint 5 Scope:
- Text campaigns supported
- Image campaigns NOT yet supported at messenger layer
- Service layer unchanged
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db import get_db
from app.messaging.client_messenger import send_message
from app.clients.fatginger.campaigns.service import (
    create_campaign,
    trigger_campaign_send,
)

logger = logging.getLogger(__name__)

templates = Jinja2Templates(directory="templates")

TENANT_PREFIX = "r_fg__"
T_CAMPAIGNS = f"{TENANT_PREFIX}campaigns"
T_LOGS = f"{TENANT_PREFIX}broadcast_logs"

# 🔒 FatGinger business number (locked for this tenant)
FATGINGER_BUSINESS_MSISDN = "27787480252"

router = APIRouter(prefix="/admin/fatginger/ui", tags=["FatGinger Campaign UI"])


# ---------------------------------------------------------
# Messaging Adapter Builders (Sprint 5 compliant)
# ---------------------------------------------------------

def _build_text_sender(db: Session):
    def _sender(phone: str, message: str) -> None:
        send_message(
            db=db,
            business_msisdn=FATGINGER_BUSINESS_MSISDN,
            to_number=phone,
            text=message,
        )
    return _sender


def _build_image_sender(db: Session):
    def _sender(phone: str, image_url: str, caption: Optional[str]) -> None:
        # Sprint 5 scope: image sending not implemented yet
        raise RuntimeError("Image sending not implemented for FatGinger in Sprint 5.")
    return _sender


# ---------------------------------------------------------
# Dashboard
# ---------------------------------------------------------

@router.get("/campaigns")
def campaign_list(
    request: Request,
    db: Session = Depends(get_db),
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


# ---------------------------------------------------------
# Create Campaign
# ---------------------------------------------------------

@router.get("/campaigns/create")
def campaign_create_form(
    request: Request,
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


# ---------------------------------------------------------
# Send Campaign
# ---------------------------------------------------------

@router.post("/campaigns/{campaign_id}/send")
def campaign_send(
    campaign_id: str,
    db: Session = Depends(get_db),
):
    trigger_campaign_send(
        db=db,
        campaign_id=campaign_id,
        send_text=_build_text_sender(db),
        send_image=_build_image_sender(db),
    )

    return RedirectResponse(
        url="/admin/fatginger/ui/campaigns",
        status_code=303,
    )


# ---------------------------------------------------------
# Logs
# ---------------------------------------------------------

@router.get("/campaigns/{campaign_id}/logs")
def campaign_logs(
    campaign_id: str,
    request: Request,
    db: Session = Depends(get_db),
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