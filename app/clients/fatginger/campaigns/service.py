from __future__ import annotations

"""
File: app/clients/fatginger/campaigns/service.py
Path: app/clients/fatginger/campaigns/service.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Sprint 5 – Broadcast Campaign Engine (FatGinger only)

This module provides:
- Create campaign (DRAFT)
- Manual trigger send (text OR image+caption)
- Delivery logging into r_fg__broadcast_logs
- STOP safety via marketing_opt_in = TRUE selection only

Rules (LOCKED):
- Tenant: FatGinger only (prefix r_fg__)
- No cross-tenant sending
- Must not modify dispatcher
- Must not affect booking/menu flows
- STOP users never included (assumed as marketing_opt_in = FALSE)
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional, Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

TENANT_PREFIX = "r_fg__"
T_CAMPAIGNS = f"{TENANT_PREFIX}campaigns"
T_CUSTOMERS = f"{TENANT_PREFIX}customers"
T_BROADCAST_LOGS = f"{TENANT_PREFIX}broadcast_logs"


# -----------------------------
# Messaging abstraction
# -----------------------------
SendTextFn = Callable[[str, str], None]
SendImageFn = Callable[[str, str, Optional[str]], None]


@dataclass(frozen=True)
class Campaign:
    id: str
    title: str
    message: str
    image_url: Optional[str]
    status: str
    created_at: datetime


def _guard_tenant_tables() -> None:
    # Hard guardrail: this service is FatGinger-only by design.
    if TENANT_PREFIX != "r_fg__":
        raise RuntimeError("TENANT_PREFIX modified unexpectedly; tenant isolation guard failed.")


# -----------------------------
# Campaign creation
# -----------------------------
def create_campaign(
    db: Session,
    *,
    title: str,
    message: str,
    image_url: Optional[str] = None,
) -> Campaign:
    """
    Creates a new campaign in DRAFT status.
    """
    _guard_tenant_tables()

    logger.info(
        "CAMPAIGN_CREATE | tenant=%s | title=%s | has_image=%s",
        TENANT_PREFIX,
        title,
        bool(image_url),
    )

    row = db.execute(
        text(
            f"""
            INSERT INTO {T_CAMPAIGNS} (title, message, image_url, status)
            VALUES (:title, :message, :image_url, 'DRAFT')
            RETURNING id, title, message, image_url, status, created_at
            """
        ),
        {"title": title, "message": message, "image_url": image_url},
    ).mappings().first()

    if not row:
        raise RuntimeError("Failed to create campaign (no row returned).")

    db.commit()

    return Campaign(
        id=str(row["id"]),
        title=row["title"],
        message=row["message"],
        image_url=row["image_url"],
        status=row["status"],
        created_at=row["created_at"],
    )


def get_campaign(db: Session, *, campaign_id: str) -> Campaign:
    """
    Fetch a campaign by id.
    """
    _guard_tenant_tables()

    row = db.execute(
        text(
            f"""
            SELECT id, title, message, image_url, status, created_at
            FROM {T_CAMPAIGNS}
            WHERE id = :id
            """
        ),
        {"id": campaign_id},
    ).mappings().first()

    if not row:
        raise ValueError(f"Campaign not found: {campaign_id}")

    return Campaign(
        id=str(row["id"]),
        title=row["title"],
        message=row["message"],
        image_url=row["image_url"],
        status=row["status"],
        created_at=row["created_at"],
    )


# -----------------------------
# Manual send trigger
# -----------------------------
def trigger_campaign_send(
    db: Session,
    *,
    campaign_id: str,
    send_text: SendTextFn,
    send_image: SendImageFn,
) -> dict:
    """
    Manual trigger only.

    - Select customers where marketing_opt_in = TRUE
    - For each customer:
        - if image_url is NULL => send text
        - else => send image + caption
    - Insert a log row per attempt
    """
    _guard_tenant_tables()

    campaign = get_campaign(db, campaign_id=campaign_id)

    logger.info(
        "CAMPAIGN_TRIGGER_SEND | tenant=%s | campaign_id=%s | status=%s | has_image=%s",
        TENANT_PREFIX,
        campaign.id,
        campaign.status,
        bool(campaign.image_url),
    )

    # Pull opted-in customers only (STOP excluded).
    customers: Sequence[dict] = db.execute(
        text(
            f"""
            SELECT phone
            FROM {T_CUSTOMERS}
            WHERE marketing_opt_in = TRUE
              AND phone IS NOT NULL
              AND phone <> ''
            """
        )
    ).mappings().all()

    total = len(customers)
    sent = 0
    failed = 0

    for c in customers:
        phone = str(c["phone"]).strip()
        status = "SENT"

        try:
            if campaign.image_url:
                send_image(phone, campaign.image_url, campaign.message)
            else:
                send_text(phone, campaign.message)

            sent += 1

        except Exception as ex:  # noqa: BLE001 (deliberate: log and continue)
            status = "FAILED"
            failed += 1
            logger.exception(
                "CAMPAIGN_SEND_FAIL | tenant=%s | campaign_id=%s | phone=%s | err=%s",
                TENANT_PREFIX,
                campaign.id,
                phone,
                str(ex),
            )

        # Log every attempt (success or failure)
        db.execute(
            text(
                f"""
                INSERT INTO {T_BROADCAST_LOGS} (
                    campaign_id,
                    customer_phone,
                    delivery_status,
                    sent_at
                )
                VALUES (
                    :campaign_id,
                    :customer_phone,
                    :delivery_status,
                    NOW()
                )
                """
            ),
            {
                "campaign_id": campaign.id,
                "customer_phone": phone,
                "delivery_status": status,
            },
        )

    db.commit()

    logger.info(
        "CAMPAIGN_TRIGGER_DONE | tenant=%s | campaign_id=%s | total=%s | sent=%s | failed=%s",
        TENANT_PREFIX,
        campaign.id,
        total,
        sent,
        failed,
    )

    return {"campaign_id": campaign.id, "total": total, "sent": sent, "failed": failed}