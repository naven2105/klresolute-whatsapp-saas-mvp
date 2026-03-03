from __future__ import annotations

"""
File: app/webhook_status_handler.py
Path: app/webhook_status_handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Handle WhatsApp "statuses"-only webhook payloads.

Rules:
- Structural parsing of statuses payload
- Persist / reconcile delivery outcomes
- NO inbound message routing
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger("webhooks.status")


def _get_entry_value(payload: dict) -> Optional[dict]:
    try:
        return payload["entry"][0]["changes"][0]["value"]
    except Exception:
        return None


def _to_local_sa_mobile(e164_or_digits: str | None) -> Optional[str]:
    """
    Convert "2773..." -> "0773..." for SA mobiles.
    FatGinger tenant tables currently store local format in r_fg__customers.phone and r_fg__broadcast_logs.customer_phone.
    """
    if not e164_or_digits:
        return None

    digits = "".join([c for c in str(e164_or_digits) if c.isdigit()])

    # If already local
    if digits.startswith("0") and 10 <= len(digits) <= 11:
        return digits

    # Convert SA E.164 (27xxxxxxxxx) -> 0xxxxxxxxx
    if digits.startswith("27") and len(digits) >= 11:
        return "0" + digits[2:]

    return None


def _parse_meta_timestamp(ts: str | int | None) -> Optional[datetime]:
    """
    Meta timestamps are commonly epoch seconds as string.
    """
    if ts is None:
        return None
    try:
        sec = int(ts)
        return datetime.fromtimestamp(sec, tz=timezone.utc)
    except Exception:
        return None


def _fg_customer_exists(db: Session, *, local_phone: str) -> bool:
    row = db.execute(
        text("SELECT 1 FROM r_fg__customers WHERE phone = :p LIMIT 1"),
        {"p": local_phone},
    ).first()
    return bool(row)


def _fg_mark_latest_log(
    db: Session,
    *,
    local_phone: str,
    new_status: str,
) -> Optional[str]:
    """
    Update the most recent SENT log for this customer to new_status.
    Returns campaign_id (uuid as text) if updated.
    """
    row = db.execute(
        text(
            """
            WITH target AS (
                SELECT id, campaign_id
                FROM r_fg__broadcast_logs
                WHERE customer_phone = :phone
                  AND delivery_status = 'SENT'
                ORDER BY sent_at DESC
                LIMIT 1
            )
            UPDATE r_fg__broadcast_logs bl
            SET delivery_status = :new_status
            FROM target
            WHERE bl.id = target.id
            RETURNING target.campaign_id::text
            """
        ),
        {"phone": local_phone, "new_status": new_status},
    ).first()

    return row[0] if row else None


def _fg_adjust_campaign_counts(
    db: Session,
    *,
    campaign_id: str,
    sent_delta: int,
    failed_delta: int,
) -> None:
    db.execute(
        text(
            """
            UPDATE r_fg__campaigns
            SET sent_count = GREATEST(sent_count + :sent_delta, 0),
                failed_count = GREATEST(failed_count + :failed_delta, 0)
            WHERE id = :cid::uuid
            """
        ),
        {"cid": campaign_id, "sent_delta": sent_delta, "failed_delta": failed_delta},
    )


def handle_status_payload(db: Session, payload: dict) -> bool:
    """
    Returns True if this payload contained statuses and was handled.
    Safe to call before normal inbound routing.
    """
    entry = _get_entry_value(payload)
    if not entry:
        return False

    statuses = entry.get("statuses") or []
    if not statuses:
        return False

    meta = entry.get("metadata", {})
    business_raw = meta.get("display_phone_number")

    handled_any = False

    for status in statuses:
        handled_any = True

        recipient_id = status.get("recipient_id")
        status_id = status.get("id")
        status_value = (status.get("status") or "").upper()
        ts = _parse_meta_timestamp(status.get("timestamp"))
        errors = status.get("errors") or []

        logger.warning(
            "STATUS_IN | business_raw=%s | recipient_id=%s | status=%s | status_id=%s | ts=%s | has_errors=%s",
            business_raw,
            recipient_id,
            status.get("status"),
            status_id,
            ts.isoformat() if ts else None,
            bool(errors),
        )

        # --- FatGinger reconciliation (tenant tables) ---
        local_phone = _to_local_sa_mobile(str(recipient_id) if recipient_id else None)
        if not local_phone:
            continue

        # Only touch FG if recipient is an FG customer
        if not _fg_customer_exists(db, local_phone=local_phone):
            continue

        # Determine desired state
        # - If Meta says failed OR errors exist => FAILED
        # - If delivered => DELIVERED
        # - Otherwise ignore (sent/read etc. can be added later without risk)
        if errors or status_value == "FAILED":
            campaign_id = _fg_mark_latest_log(
                db,
                local_phone=local_phone,
                new_status="FAILED",
            )
            if campaign_id:
                _fg_adjust_campaign_counts(
                    db,
                    campaign_id=campaign_id,
                    sent_delta=-1,
                    failed_delta=+1,
                )
                db.commit()

            # Log error details for traceability
            for e in errors:
                logger.warning(
                    "STATUS_ERROR | local_phone=%s | recipient_id=%s | status_id=%s | code=%s | title=%s | message=%s | details=%s",
                    local_phone,
                    recipient_id,
                    status_id,
                    e.get("code"),
                    e.get("title"),
                    e.get("message"),
                    e.get("error_data") or e.get("details") or e,
                )

        elif status_value == "DELIVERED":
            campaign_id = _fg_mark_latest_log(
                db,
                local_phone=local_phone,
                new_status="DELIVERED",
            )
            if campaign_id:
                db.commit()

    return handled_any