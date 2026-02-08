from __future__ import annotations

"""
File: app/webhooks.py
Path: app/webhooks.py
Project: KLResolute WhatsApp SaaS MVP

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
        logger.warning("MSISDN_NORMALISE_SKIP | reason=empty")
        return None

    digits = re.sub(r"\D", "", raw)

    if digits.startswith("0"):
        digits = "27" + digits[1:]

    if digits.startswith("27") and len(digits) >= 11:
        logger.info("MSISDN_NORMALISED | raw=%s | normalised=%s", raw, digits)
        return digits

    logger.error("MSISDN_NORMALISE_FAIL | raw=%s | digits=%s", raw, digits)
    return None


def _extract_message(payload: dict):
    try:
        logger.info(
            "WEBHOOK_RAW_PAYLOAD_KEYS | keys=%s",
            list(payload.keys()),
        )

        entry = payload["entry"][0]["changes"][0]["value"]

        logger.info(
            "WEBHOOK_VALUE_KEYS | keys=%s",
            list(entry.keys()),
        )

        messages = entry.get("messages")
        statuses = entry.get("statuses")

        # -------------------------
        # STATUS-ONLY PAYLOAD
        # -------------------------
        if not messages and statuses:
            meta = entry.get("metadata", {})
            status = statuses[0]

            logger.warning(
                "PAYLOAD_STATUS_ONLY | "
                "business_raw=%s | "
                "recipient_id=%s | "
                "status=%s | "
                "status_id=%s | "
                "timestamp=%s | "
                "conversation=%s",
                meta.get("display_phone_number"),
                status.get("recipient_id"),
                status.get("status"),
                status.get("id"),
                status.get("timestamp"),
                status.get("conversation"),
            )
            return None, None, None, None

        if not messages:
            logger.warning(
                "PAYLOAD_NO_MESSAGES | has_statuses=%s",
                bool(statuses),
            )
            return None, None, None, None

        # -------------------------
        # MESSAGE PAYLOAD
        # -------------------------
        msg = messages[0]
        sender_raw = msg.get("from")
        provider_message_id = msg.get("id")
        business_raw = entry.get("metadata", {}).get("display_phone_number")

        logger.info(
            "MESSAGE_RAW_FIELDS | sender_raw=%s | business_raw=%s | pid=%s | msg_keys=%s",
            sender_raw,
            business_raw,
            provider_message_id,
            list(msg.keys()),
        )

        sender = _normalise_msisdn(sender_raw)
        business = _normalise_msisdn(business_raw)

        logger.info(
            "MESSAGE_EXTRACTED | type=%s | sender=%s | business=%s | pid=%s",
            msg.get("type"),
            sender,
            business,
            provider_message_id,
        )

        return msg, sender, business, provider_message_id

    except Exception:
        logger.exception("PAYLOAD_EXTRACT_FAIL")
        return None, None, None, None


def _try_lock_provider_message(db: Session, provider_message_id: str) -> bool:
    if not provider_message_id:
        logger.warning("DEDUPE_SKIP | reason=no_provider_message_id")
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

        locked = bool(getattr(result, "rowcount", 0) == 1)

        logger.info(
            "DEDUPE_RESULT | pid=%s | locked=%s",
            provider_message_id,
            locked,
        )

        return locked

    except Exception:
        db.rollback()
        logger.exception("DEDUPE_LOCK_FAIL | pid=%s", provider_message_id)
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
            logger.error(
                "CLIENT_ID_INT_NOT_FOUND | business=%s",
                business_msisdn,
            )
            return None

        logger.info(
            "CLIENT_ID_INT_RESOLVED | business=%s | client_id=%s",
            business_msisdn,
            row["klresolute_client_id"],
        )

        return int(row["klresolute_client_id"])

    except Exception:
        logger.exception(
            "CLIENT_ID_INT_LOOKUP_FAIL | business=%s",
            business_msisdn,
        )
        return None


def _is_active_galitos_staff(db: Session, *, sender_msisdn: str) -> bool:
    """
    Receive-only guard:
    If sender is an active Galitos staff number, ignore inbound messages to prevent
    opening a 24-hour session window and/or routing staff into customer menu flows.
    """
    try:
        row = (
            db.execute(
                text(
                    """
                    SELECT 1
                    FROM galitos_staff
                    WHERE msisdn = :msisdn
                      AND is_active = true
                    LIMIT 1
                    """
                ),
                {"msisdn": sender_msisdn},
            )
            .first()
        )

        is_staff = bool(row)
        logger.info(
            "STAFF_INBOUND_CHECK | sender=%s | is_active_staff=%s",
            sender_msisdn,
            is_staff,
        )
        return is_staff

    except Exception:
        logger.exception("STAFF_INBOUND_CHECK_FAIL | sender=%s", sender_msisdn)
        return False


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

    msg, sender, business_msisdn, provider_message_id = _extract_message(payload)

    if not msg or not sender or not business_msisdn:
        logger.error(
            "WEBHOOK_ABORT_DETAIL | reason=missing_fields | msg=%s | sender=%s | business=%s | pid=%s",
            bool(msg),
            sender,
            business_msisdn,
            provider_message_id,
        )
        return Response(status_code=200)

    # DB guard
    try:
        db.execute(text("SELECT 1"))
        logger.info("DB_OK")
    except OperationalError:
        logger.critical("DB_UNAVAILABLE | sender=%s", sender)
        send_message(
            to_number=sender,
            text="⚠️ Service temporarily unavailable. Please try again shortly.",
        )
        return Response(status_code=200)

    # -------------------------------------------------
    # Receive-only guard: ignore Galitos staff inbound
    # -------------------------------------------------
    if _is_active_galitos_staff(db, sender_msisdn=sender):
        logger.warning(
            "WEBHOOK_ABORT | reason=staff_inbound_blocked | sender=%s | business=%s",
            sender,
            business_msisdn,
        )
        return Response(status_code=200)

    # Dedupe
    if not _try_lock_provider_message(db, provider_message_id):
        logger.warning(
            "WEBHOOK_ABORT | reason=duplicate | pid=%s",
            provider_message_id,
        )
        return Response(status_code=200)

    # Maintenance
    try:
        auto_close_expired_inspections(db)
        logger.info("AUTO_CLOSE_CHECK_DONE")
    except Exception:
        logger.exception("AUTO_CLOSE_FAIL")

    # Dispatch
    logger.info(
        "DISPATCH_CALL | sender=%s | business=%s | msg_type=%s",
        sender,
        business_msisdn,
        msg.get("type"),
    )

    handled = dispatch(
        db=db,
        msg=msg,
        sender=sender,
        business_msisdn=business_msisdn,
    )

    logger.info(
        "DISPATCH_RETURN | handled=%s | sender=%s",
        handled,
        sender,
    )

    # Tier-1 fallback
    if not handled:
        body = (
            msg.get("text", {}).get("body", "").strip()
            if msg.get("type") == "text"
            else ""
        )

        logger.warning(
            "FALLBACK_EVAL | sender=%s | body=%r",
            sender,
            body,
        )

        if body.upper() not in ("YES", "NO"):
            client_id_int = _resolve_integer_client_id(
                db,
                business_msisdn=business_msisdn,
            )

            if client_id_int is None:
                logger.error(
                    "FALLBACK_ABORT | reason=client_id_not_resolved | sender=%s",
                    sender,
                )
            else:
                logger.info(
                    "FALLBACK_TIER1_CALL | sender=%s | client_id=%s",
                    sender,
                    client_id_int,
                )

                handle_client_command(
                    db=db,
                    sender_number=sender,
                    message_text=body,
                    msg=msg,
                    resolved_client_id=str(client_id_int),
                    resolved_business_number=business_msisdn,
                )

    logger.info(
        "WEBHOOK_COMPLETE | sender=%s | business=%s",
        sender,
        business_msisdn,
    )

    return Response(status_code=200)
