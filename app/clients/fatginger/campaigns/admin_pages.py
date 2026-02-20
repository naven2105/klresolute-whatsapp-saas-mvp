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

NOTE:
UI routes are intentionally NOT protected by header-based admin auth.
This allows browser-based dashboard usage.
"""

import logging
from typing import Optional, Callable, Any

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db import get_db

from app.clients.fatginger.campaigns.service import (
    create_campaign,
    trigger_campaign_send,
)

# Import messenger module safely
from app.messaging import client_messenger as cm

logger = logging.getLogger(__name__)

templates = Jinja2Templates(directory="templates")

TENANT_PREFIX = "r_fg__"
T_CAMPAIGNS = f"{TENANT_PREFIX}campaigns"
T_LOGS = f"{TENANT_PREFIX}broadcast_logs"

router = APIRouter(prefix="/admin/fatginger/ui", tags=["FatGinger Campaign UI"])


# ---------------------------------------------------------
# Messenger Adapters
# ---------------------------------------------------------

def _first_callable(*names: str) -> Optional[Callable[..., Any]]:
    for n in names:
        fn = getattr(cm, n, None)
        if callable(fn):
            return fn
    return None


def _send_text(phone: str, message: str) -> None:
    fn = _first_callable("send_text_message", "send_message", "send_text")
    if not fn:
        raise RuntimeError("No text send function found in app.messaging.client_messenger")

    try:
        fn(phone, message)
        return
    except TypeError:
        pass

    try:
        fn(to=phone, text=message)
        return
    except TypeError:
        pass

    try:
        fn(to=phone, message=message)
        return
    except TypeError:
        pass

    raise RuntimeError("Text send function exists but signature is incompatible.")


def _send_image(phone: str, image_url: str, caption: Optional[str]) -> None:
    fn = _first_callable(
        "send_image_message",
        "send_media_message",
        "send_media",
        "send_image",
    )
    if not fn:
        raise RuntimeError("No image/media send function found in app.messaging.client_messenger")

    try:
        fn(phone, image_url, caption)
        return
    except TypeError:
        pass

    try:
        fn(phone, image_url, caption=caption)
        return
    except TypeError:
        pass

    try:
        fn(to=phone, image_url=image_url, caption=caption)
        return
    except TypeError:
        pass

    try:
        fn(to=phone, media_url=image_url, caption=caption)
        return
    except TypeError:
        pass

    raise RuntimeError("Image/media send function exists but signature is incompatible.")


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
        send_text=_send_text,
        send_image=_send_image,
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