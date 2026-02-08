from __future__ import annotations

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.outbound.meta import MetaWhatsAppClient
from app.outbound.settings import load_meta_settings

logger = logging.getLogger("galitos_staff_notifier")

_meta_client = MetaWhatsAppClient(settings=load_meta_settings())


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

    try:
        rows = db.execute(
            text(
                """
                SELECT msisdn
                FROM galitos_staff
                WHERE klresolute_client_id = :client_id
                  AND is_active = true
                """
            ),
            {"client_id": client_id},
        ).fetchall()
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

    for r in rows:
        try:
            logger.info(
                "ORDER_STAFF_NOTIFY_SEND | client_id=%s | msisdn=%s",
                client_id,
                r.msisdn,
            )

            result = _meta_client.send_generic_business_update_template(
                to_msisdn=r.msisdn,
                blob_text=message,
            )

            logger.info(
                "ORDER_STAFF_NOTIFY_META_RESPONSE | "
                "client_id=%s | msisdn=%s | success=%s | message_id=%s | error=%s",
                client_id,
                r.msisdn,
                getattr(result, "success", None),
                getattr(result, "message_id", None),
                getattr(result, "error", None),
            )

        except Exception:
            logger.exception(
                "ORDER_STAFF_NOTIFY_SEND_FAIL | client_id=%s | msisdn=%s",
                client_id,
                r.msisdn,
            )
