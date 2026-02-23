from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Request, Form
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

FATGINGER_BUSINESS_MSISDN = "27787480252"

router = APIRouter(prefix="/admin/fatginger/ui", tags=["FatGinger Campaign UI"])


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
        raise RuntimeError("Image sending not implemented.")
    return _sender


@router.get("/campaigns")
def campaign_dashboard(request: Request, db: Session = Depends(get_db)):

    rows = db.execute(
        text(
            f"""
            SELECT id, title, status, created_at
            FROM {T_CAMPAIGNS}
            ORDER BY created_at DESC
            """
        )
    ).mappings().all()

    return templates.TemplateResponse(
        "campaign_list.html",
        {"request": request, "campaigns": rows},
    )


@router.post("/campaigns")
def create_and_send(
    request: Request,
    title: str = Form(...),
    message: str = Form(...),
    image_url: str = Form(""),
    db: Session = Depends(get_db),
):

    campaign = create_campaign(
        db=db,
        title=title,
        message=message,
        image_url=image_url or None,
    )

    trigger_campaign_send(
        db=db,
        campaign_id=campaign.id,
        send_text=_build_text_sender(db),
        send_image=_build_image_sender(db),
    )

    rows = db.execute(
        text(
            f"""
            SELECT id, title, status, created_at
            FROM {T_CAMPAIGNS}
            ORDER BY created_at DESC
            """
        )
    ).mappings().all()

    return templates.TemplateResponse(
        "campaign_list.html",
        {"request": request, "campaigns": rows},
    )