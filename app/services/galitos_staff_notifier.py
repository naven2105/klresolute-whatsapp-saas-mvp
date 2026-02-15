from __future__ import annotations

"""
File: app/services/galitos_staff_notifier.py
Path: app/services/galitos_staff_notifier.py
Project: KLResolute WhatsApp SaaS MVP

Sprint: Full UUID Identity Migration

Purpose:
Notify Galitos staff when a customer order is confirmed.

Changes:
- Removed klresolute_client_id usage
- UUID-only identity resolution
- Defensive rollback protection
- No behavioural changes
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.outbound.factory import get_meta_client

logger = logging.getLogger("galitos_staff_notifier")

STAFF_TEMPLATE_NAME = "generic_business_update"


def notify_galitos_staff(
    *,
    db: Session,
    client_id: str,  # UUID
    message: str,
) -> None:

    logger.info(
        "ORDER_STAFF_NOTIFY_ENTER | client_id=%s | message=%r",
        client_id,
        message,
    )

    # Defensive rollback
    try:
        db.rollback()
    except Exception:
        logger.exception("ORDER_STAFF_NOTIFY_DB_RESET_FAIL | client_id=%s", client_id)

    # -------------------------------------------------
    # Resolve business_msisdn via UUID
    # -------------------------------------------------
    try:
        business_row = (
            db.execute(
                text(
                    """
                    SELECT destination_number
                    FROM whatsapp_numbers
                    WHERE client_id = :client_id
                      AND status = 'active'
                    LIMIT 1
                    """
                ),
                {"client_id": client_id},
            )
            .mappings()
            .first()
        )
    except Exception:
        logger.exception(
            "ORDER_STAFF_NOTIFY_BUSINESS_LOOKUP_FAIL | client_id=%s",
            client_id,
        )
        return

    if not business_row:
        logger.error(
            "ORDER_STAFF_NOTIFY_ABORTED | reason=no_business_number | client_id=%s",
            client_id,
        )
        return

    business_msisdn = business_row["destination_number"]

    # -------------------------------------------------
    # Fetch active staff (UUID-based)
    # -------------------------------------------------
    try:
        rows = (
            db.execute(
                text(
                    """
                    SELECT msisdn
                    FROM galitos_staff
                    WHERE client_id = :client_id
                      AND is_active = true
                    """
                ),
                {"client_id": client_id},
            )
            .mappings()
            .all()
        )
    except Exception:
        logger.exception(
            "ORDER_STAFF_NOTIFY_QUERY_FAIL | client_id=%s",
            client_id,
        )
        return

    logger.info(
        "ORDER_STAFF_NOTIFY_ROWS | client_id=%s | count=%s",
        client_id,
        len(rows),
    )

    if not rows:
        logger.error(
            "ORDER_STAFF_NOTIFY_ABORTED | reason=no_active_staff | client_id=%s",
            client_id,
        )
        return

    # -------------------------------------------------
    # Send via TEMPLATE (always)
    # -------------------------------------------------
    meta = get_meta_client(business_msisdn=business_msisdn)

    for r in rows:
        msisdn = r["msisdn"]

        try:
            logger.info(
                "ORDER_STAFF_NOTIFY_SEND_TEMPLATE | client_id=%s | msisdn=%s",
                client_id,
                msisdn,
            )

            meta.send_template(
                to_msisdn=msisdn,
                template_name=STAFF_TEMPLATE_NAME,
                language_code="en_US",
                body_params=[message],
            )

            logger.info(
                "ORDER_STAFF_NOTIFY_SENT | client_id=%s | msisdn=%s",
                client_id,
                msisdn,
            )

        except Exception:
            logger.exception(
                "ORDER_STAFF_NOTIFY_SEND_FAIL | client_id=%s | msisdn=%s",
                client_id,
                msisdn,
            )
