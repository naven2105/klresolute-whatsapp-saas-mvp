from __future__ import annotations

"""
File: app/clients/fatginger/campaigns/service.py
Sprint 5 – Broadcast Campaign Engine (FatGinger only)
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
    if TENANT_PREFIX != "r_fg__":
        raise RuntimeError("TENANT_PREFIX modified unexpectedly.")


def create_campaign(
    db: Session,
    *,
    title: str,
    message: str,
    image_url: Optional[str] = None,
) -> Campaign:

    _guard_tenant_tables()

    row = db.execute(
        text(
            f"""
            INSERT INTO {T_CAMPAIGNS} (title, message, image_url, status)
            VALUES (:title, :message, :image_url, 'SENT')
            RETURNING id, title, message, image_url, status, created_at
            """
        ),
        {"title": title, "message": message, "image_url": image_url},
    ).mappings().first()

    db.commit()

    return Campaign(
        id=str(row["id"]),
        title=row["title"],
        message=row["message"],
        image_url=row["image_url"],
        status=row["status"],
        created_at=row["created_at"],
    )


def trigger_campaign_send(
    db: Session,
    *,
    campaign_id: str,
    send_text: SendTextFn,
    send_image: SendImageFn,
) -> dict:

    _guard_tenant_tables()

    campaign = db.execute(
        text(
            f"""
            SELECT id, title, message, image_url
            FROM {T_CAMPAIGNS}
            WHERE id = :id
            """
        ),
        {"id": campaign_id},
    ).mappings().first()

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
            if campaign["image_url"]:
                send_image(phone, campaign["image_url"], campaign["message"])
            else:
                send_text(phone, campaign["message"])
            sent += 1
        except Exception:
            status = "FAILED"
            failed += 1
            logger.exception(
                "CAMPAIGN_SEND_FAIL | tenant=%s | campaign_id=%s | phone=%s",
                TENANT_PREFIX,
                campaign_id,
                phone,
            )

        db.execute(
            text(
                f"""
                INSERT INTO {T_BROADCAST_LOGS}
                (campaign_id, customer_phone, delivery_status, sent_at)
                VALUES (:campaign_id, :customer_phone, :delivery_status, NOW())
                """
            ),
            {
                "campaign_id": campaign_id,
                "customer_phone": phone,
                "delivery_status": status,
            },
        )

    db.commit()

    return {"campaign_id": campaign_id, "total": total, "sent": sent, "failed": failed}