from __future__ import annotations

"""
File: app/webhooks.py
Project: KLResolute WhatsApp SaaS MVP
"""

import logging
import re
from typing import Optional

from fastapi import APIRouter, Request, Response, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.db import get_db
from app.inbound_dispatcher import dispatch
from app.handlers.tier1_router import handle_client_command
from app.clients.magen.auto_close import auto_close_expired_inspections
from app.messaging.client_messenger import send_message

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger("webhooks")


# -------------------------------------------------
# Helpers
# -------------------------------------------------

def _normalise_msisdn(raw: str | None) -> Optional[str]:
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("0"):
        digits = "27" + digits[1:]
    if digits.startswith("27") and len(digits) >= 11:
        return digits
    return None


def _extract_message(payload: dict):
    try:
        entry = payload["entry"][0]["changes"][0]["value"]

        messages = entry.get("messages")
        if not messages:
            return None, None, None, None

        msg = messages[0]
        sender = msg.get("from")
        provider_message_id = msg.get("id")
        business_raw = entry.get("metadata", {}).get("display_phone_number")

        return (
            msg,
            _normalise_msisdn(sender),
            _normalise_msisdn(business_raw),
            provider_message_id,
        )

    except Exception:
        return None, None, None, None


def _try_lock_provider_message(db: Session, provider_message_id: str) -> bool:
    if not provider_message_id:
        return True

    try:
        result = db.execute(
            text(
                """
                INSERT INTO inbound_message_dedupe (provider_message_id)
                VALUES (:pid)
                ON CONFLICT (provider_message_id) DO NOTHING
                """
            ),
            {"pid": provider_message_id},
        )
        db.commit()
        return bool(getattr(result, "rowcount", 0) == 1)

    except Exception:
        db.rollback()
        return True


def _resolve_integer_client_id(
    db: Session,
    *,
    business_msisdn: str,
) -> int | None:
    try:
        row = (
            db.execute(
                text(
                    """
                    SELECT klresolute_client_id
                    FROM whatsapp_numbers
                    WHERE destination_number = :business
                      AND status = 'active'
                    LIMIT 1
                    """
                ),
                {"business": business_msisdn},
            )
            .mappings()
            .first()
        )

        if not row or row["klresolute_client_id"] is None:
            return None

        return int(row["klresolute_client_id"])

    except Exception:
        return None


# -------------------------------------------------
# Webhook
# -------------------------------------------------

@router.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    payload = await request.json()
    msg, sender, business_msisdn, provider_message_id = _extract_message(payload)

    if not msg or not sender or not business_msisdn:
        return Response(status_code=200)

    # DB guard
    try:
        db.execute(text("SELECT 1"))
    except OperationalError:
        send_message(
            to_number=sender,
            text="⚠️ Service temporarily unavailable. Please try again shortly.",
        )
        return Response(status_code=200)

    if not _try_lock_provider_message(db, provider_message_id):
        return Response(status_code=200)

    try:
        auto_close_expired_inspections(db)
    except Exception:
        pass

    # -----------------------------
    # Dispatch (modules + routing)
    # -----------------------------
    handled = dispatch(
        db=db,
        msg=msg,
        sender=sender,
        business_msisdn=business_msisdn,
    )

    # -----------------------------
    # Tier-1 fallback (GUARDED)
    # -----------------------------
    if not handled:
        body = (
            msg.get("text", {}).get("body", "").strip()
            if msg.get("type") == "text"
            else ""
        )

        if body.upper() not in ("YES", "NO"):
            client_id_int = _resolve_integer_client_id(
                db,
                business_msisdn=business_msisdn,
            )

            if client_id_int is None:
                logger.error(
                    "WEBHOOK_FALLBACK_BLOCKED | reason=client_id_not_resolved | business=%s | sender=%s",
                    business_msisdn,
                    sender,
                )
            else:
                handle_client_command(
                    db=db,
                    sender_number=sender,
                    message_text=body,
                    msg=msg,
                    resolved_client_id=str(client_id_int),
                    resolved_business_number=business_msisdn,
                )

    return Response(status_code=200)
