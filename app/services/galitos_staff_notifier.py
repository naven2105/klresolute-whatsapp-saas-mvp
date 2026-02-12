from __future__ import annotations

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.messaging.client_messenger import send_message

logger = logging.getLogger("galitos_staff_notifier")


def notify_galitos_staff(
    *,
    db: Session,
    client_id: int,
    message: str,
) -> None:
    logger.info(
        "ORDER_STAFF_NOTIFY_ENTER | client_id=%s | message=%r",
        client_id,
        message,
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
    # Send via single transport gateway
    # -------------------------------------------------
    for r in rows:
        msisdn = r["msisdn"]

        try:
            logger.info(
                "ORDER_STAFF_NOTIFY_SEND | client_id=%s | msisdn=%s",
                client_id,
                msisdn,
            )

            send_message(
                db=db,
                business_msisdn=business_msisdn,
                to_number=msisdn,
                text=message,
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
