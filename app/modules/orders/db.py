from __future__ import annotations

"""
File: app/modules/orders/db.py
Path: app/modules/orders/db.py
Project: KLResolute WhatsApp SaaS MVP

Sprint: Full UUID Identity Migration

Purpose:
Database access helpers for Orders module.

Rules (LOCKED):
- READ helpers only
- No messaging
- No business logic
- UUID client_id only
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger("module.orders.db")


def get_active_order_state(db: Session, sender: str) -> dict | None:
    row = (
        db.execute(
            text(
                """
                SELECT *
                FROM conversation_state
                WHERE sender_msisdn = :sender
                  AND active = true
                  AND state_type = 'ORDER'
                ORDER BY started_at DESC
                LIMIT 1
                """
            ),
            {"sender": sender},
        )
        .mappings()
        .first()
    )

    if not row:
        logger.info("ORDERS_STATE_NONE | sender=%s", sender)
        return None

    logger.info(
        "ORDERS_STATE_ACTIVE | sender=%s | state_id=%s",
        sender,
        row.get("id"),
    )
    return dict(row)


def get_client_uuid(db: Session, business_msisdn: str) -> str | None:
    """
    UUID-only client resolution.
    """
    row = (
        db.execute(
            text(
                """
                SELECT client_id
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

    if not row or not row.get("client_id"):
        logger.error(
            "ORDERS_CLIENT_UUID_LOOKUP_FAIL | business=%s",
            business_msisdn,
        )
        return None

    logger.info(
        "ORDERS_CLIENT_UUID_RESOLVED | business=%s | client_id=%s",
        business_msisdn,
        row["client_id"],
    )

    return str(row["client_id"])


def get_active_staff_numbers(db: Session) -> list[str]:
    try:
        rows = (
            db.execute(
                text(
                    """
                    SELECT msisdn
                    FROM galitos_staff
                    WHERE is_active = true
                    ORDER BY msisdn
                    """
                )
            )
            .scalars()
            .all()
        )

        if not rows:
            logger.error("ORDERS_STAFF_EMPTY | table=galitos_staff")
            return []

        logger.info(
            "ORDERS_STAFF_RESOLVED | count=%s | staff=%s",
            len(rows),
            ",".join(rows),
        )
        return rows

    except Exception as exc:
        logger.exception("ORDERS_STAFF_LOOKUP_FAIL | err=%s", exc)
        return []
