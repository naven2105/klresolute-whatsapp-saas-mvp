from __future__ import annotations

"""
File: app/handlers/galitos_staff_notifier.py
Path: app/handlers/galitos_staff_notifier.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Notify Galitos staff of confirmed customer orders.

Responsibilities (LOCKED):
- Fetch active staff for a klresolute_client_id (integer)
- Resolve correct business_msisdn (UUID client link)
- Send notification to each staff member
- Log every decision and failure
- Use SINGLE transport gateway (client_messenger)
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.messaging.client_messenger import send_message

logger = logging.getLogger("galitos.staff.notifier")


def notify_galitos_staff(
    *,
    db: Session,
    client_id: int,
    message: str,
) -> None:
    logger.info(
        "STAFF_NOTIFY_ENTER | client_id=%s | message_len=%s",
        client_id,
        len(message),
    )

    # -------------------------------------------------
    # Resolve business_msisdn (required by gateway)
    # -------------------------------------------------
    try:
        business_row = (
            db.execute(
                text(
                    """
                    SELECT destination_number
                    FROM whatsapp_numbers
                    WHERE klresolute_client_id = :client_id
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
            "STAFF_NOTIFY_BUSINESS_LOOKUP_FAIL | client_id=%s",
            client_id,
        )
        return

    if not business_row:
        logger.error(
            "STAFF_NOTIFY_ABORT | reason=no_business_number | client_id=%s",
            client_id,
        )
        return

    business_msisdn = business_row["destination_number"]

    # -------------------------------------------------
    # Fetch active staff
    # -------------------------------------------------
    try:
        rows = (
            db.execute(
                text(
                    """
                    SELECT msisdn
                    FROM galitos_staff
                    WHERE klresolute_client_id = :client_id
                      AND is_active = TRUE
                    """
                ),
                {"client_id": client_id},
            )
            .mappings()
            .all()
        )
    except Exception:
        logger.exception(
            "STAFF_NOTIFY_QUERY_FAIL | client_id=%s",
            client_id,
        )
        return

    if not rows:
        logger.error(
            "STAFF_NOTIFY_NONE_FOUND | client_id=%s",
            client_id,
        )
        return

    logger.info(
        "STAFF_NOTIFY_TARGETS | client_id=%s | count=%s",
        client_id,
        len(rows),
    )

    # -------------------------------------------------
    # Send via single transport gateway
    # -------------------------------------------------
    for r in rows:
        msisdn = r["msisdn"]

        try:
            logger.info(
                "STAFF_NOTIFY_SEND | client_id=%s | msisdn=%s",
                client_id,
                msisdn,
            )

            send_message(
                db=db,
                business_msisdn=business_msisdn,
                to_number=msisdn,
                template_name="generic_business_update",
                language_code="en_US",
            )

            logger.info(
                "STAFF_NOTIFY_SENT | client_id=%s | msisdn=%s",
                client_id,
                msisdn,
            )

        except Exception:
            logger.exception(
                "STAFF_NOTIFY_SEND_FAIL | client_id=%s | msisdn=%s",
                client_id,
                msisdn,
            )

            
