"""
File: app/main.py

Project: KLResolute WhatsApp SaaS MVP

Purpose:
Application entry point.
Responsible only for:
- FastAPI app creation
- Router registration
- Meta WhatsApp webhook verification (GET)
- Health check endpoint
- T-18 Admin router registration (read-only)

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
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse

from app.webhooks import router as webhooks_router  # BRS-driven webhook pipeline
from app.admin.routes import router as admin_router  # T-18 read-only admin endpoints

app = FastAPI()

# -------------------------------------------------------------------
# Webhook routes (POST /webhooks/whatsapp)
# -------------------------------------------------------------------
app.include_router(webhooks_router)

# -------------------------------------------------------------------
# T-18: Admin visibility (read-only)
# -------------------------------------------------------------------
app.include_router(admin_router)

# -------------------------------------------------------------------
# T-12: Meta webhook verification (GET)
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
