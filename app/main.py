from __future__ import annotations

"""
File: app/main.py
Path: app/main.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Application entry point.
Responsible only for:
- FastAPI app creation
- Router registration
- Meta WhatsApp webhook verification (GET)
- Health check endpoint
- Admin router registration
- Startup wiring (background jobs only)

Design principles:
- No business logic in this file
- No database access
- No outbound message creation
- All inbound WhatsApp processing is delegated to app.webhooks
- POST /webhooks/whatsapp is defined exactly once via router inclusion

Change policy:
- This file must remain thin and declarative
- Any behavioural change requires explicit agreement
"""

import os
import asyncio
import logging
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from app.webhooks import router as webhooks_router
from app.admin.routes import router as admin_router
from app.clients.magen.admin.routes import router as magen_admin_router
from app.clients.fatginger.campaigns.admin_routes import (
    router as fg_campaign_admin_router,
)
from app.clients.fatginger.campaigns.admin_pages import (
    router as fg_campaign_ui_router,
)

from app.modules.survey.survey_expiry_notifier import start_survey_expiry_notifier
from app.clients.magen.inspection.auto_close_worker import (
    auto_close_expired_inspections,
)

from app.db import SessionLocal

logger = logging.getLogger("main")

# -------------------------------------------------------------------
# App
# -------------------------------------------------------------------
app = FastAPI()

# -------------------------------------------------------------------
# Absolute Path Setup (Production-safe)
# -------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent  # project root
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# -------------------------------------------------------------------
# Webhook routes
# -------------------------------------------------------------------
app.include_router(webhooks_router)

# -------------------------------------------------------------------
# Admin visibility (read-only)
# -------------------------------------------------------------------
app.include_router(admin_router)

# Magen admin
app.include_router(magen_admin_router)

# FatGinger campaign admin (API endpoints)
app.include_router(fg_campaign_admin_router)

# FatGinger campaign admin (HTML UI)
app.include_router(fg_campaign_ui_router)

# -------------------------------------------------------------------
# Background worker: Magen auto-close
# -------------------------------------------------------------------
async def magen_auto_close_loop() -> None:
    logger.info("MAGEN_AUTO_CLOSE_WORKER_START")

    while True:
        try:
            db = SessionLocal()
            auto_close_expired_inspections(db)
        except Exception:
            logger.exception("MAGEN_AUTO_CLOSE_WORKER_FAIL")
        finally:
            db.close()

        await asyncio.sleep(60)

# -------------------------------------------------------------------
# Startup
# -------------------------------------------------------------------
@app.on_event("startup")
async def startup() -> None:
    start_survey_expiry_notifier()
    asyncio.create_task(magen_auto_close_loop())

# -------------------------------------------------------------------
# Meta webhook verification (GET)
# -------------------------------------------------------------------
@app.get("/webhooks/whatsapp", response_class=PlainTextResponse)
def verify_webhook(request: Request):
    params = request.query_params

    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == os.getenv("META_VERIFY_TOKEN") and challenge:
        return challenge

    raise HTTPException(status_code=403, detail="Webhook verification failed")

# -------------------------------------------------------------------
# Health
# -------------------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok"}