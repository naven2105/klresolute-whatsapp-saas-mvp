from __future__ import annotations

"""
File: app/webhooks.py
Path: app/webhooks.py
Project: KLResolute WhatsApp SaaS MVP

Sprint: Full UUID Identity Migration

Purpose:
Inbound WhatsApp webhook entry point.

Responsibilities (LOCKED):
- Parse inbound Meta payload
- Normalise MSISDNs
- Guard DB availability
- Deduplicate provider messages
- Dispatch to module router
- Fallback to Tier-1 routing

This file MUST explain, via logs, why a message:
- was ignored
- was handled
- was dispatched
- fell through
"""

import logging

from fastapi import APIRouter, Request, Response, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.webhook_extract import extract_message
from app.webhook_guards import (
    guard_db_available_or_notify,
    guard_magen_internal_only,
    guard_scoped_galitos_staff_block,
)
from app.webhook_dedupe import try_lock_provider_message
from app.webhook_dispatch import dispatch_and_fallback
from app.webhook_status_handler import handle_status_payload

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger("webhooks")


# -------------------------------------------------
# Webhook
# -------------------------------------------------

@router.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    payload = await request.json()

    logger.info(
        "WEBHOOK_IN | content_length=%s",
        request.headers.get("content-length"),
    )

    # ✅ Handle statuses-only payloads (delivery receipts / failures)
    # This must occur BEFORE normal inbound extraction aborts.
    try:
        if handle_status_payload(db, payload):
            logger.info("WEBHOOK_STATUS_HANDLED")
            return Response(status_code=200)
    except Exception:
        logger.exception("WEBHOOK_STATUS_HANDLE_FAIL")
        # Continue into normal extraction path (never block inbound handling)

    msg, sender, business_msisdn, provider_message_id = extract_message(payload)

    if not msg or not sender or not business_msisdn:
        logger.error(
            "WEBHOOK_ABORT_DETAIL | reason=missing_fields | msg=%s | sender=%s | business=%s | pid=%s",
            bool(msg),
            sender,
            business_msisdn,
            provider_message_id,
        )
        return Response(status_code=200)

    # 🔥 Guaranteed-visible marker (stdout)
    print(
        f"🔥 WEBHOOK_MSG_IN | sender={sender} | business={business_msisdn} | type={msg.get('type')} | pid={provider_message_id}"
    )
    logger.warning(
        "WEBHOOK_MSG_IN | sender=%s | business=%s | type=%s | pid=%s",
        sender,
        business_msisdn,
        msg.get("type"),
        provider_message_id,
    )

    if not guard_db_available_or_notify(
        db=db,
        sender=sender,
        business_msisdn=business_msisdn,
    ):
        return Response(status_code=200)

    # 🔒 Magen Enforcement
    if not guard_magen_internal_only(
        db=db,
        sender=sender,
        business_msisdn=business_msisdn,
    ):
        return Response(status_code=200)

    # ✅ Scoped Rustic Barrel Guard (FIX)
    if not guard_scoped_rusticbarrel_staff_block(
        db=db,
        sender=sender,
        business_msisdn=business_msisdn,
    ):
        return Response(status_code=200)

    if not try_lock_provider_message(db, provider_message_id):
        logger.warning(
            "WEBHOOK_ABORT | reason=duplicate | pid=%s",
            provider_message_id,
        )
        return Response(status_code=200)

    dispatch_and_fallback(
        db=db,
        msg=msg,
        sender=sender,
        business_msisdn=business_msisdn,
    )

    logger.info(
        "WEBHOOK_COMPLETE | sender=%s | business=%s",
        sender,
        business_msisdn,
    )

    return Response(status_code=200)