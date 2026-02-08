from __future__ import annotations

"""
File: app/handlers/galitos_staff_notifier.py
Path: app/handlers/galitos_staff_notifier.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Notify Galitos staff of confirmed customer orders.

Responsibilities (LOCKED):
- Fetch active staff for a klresolute_client_id
- Send notification to each staff member
- Log every decision and failure
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.outbound.meta import MetaWhatsAppClient
from app.outbound.settings import load_meta_settings

logger = logging.getLogger("galitos.staff.notifier")

_meta_client = MetaWhatsAppClient(settings=load_meta_settings())


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

    for r in rows:
        msisdn = r["msisdn"]

        try:
            logger.info(
                "STAFF_NOTIFY_SEND | client_id=%s | msisdn=%s",
                client_id,
                msisdn,
            )

            resp = _meta_client.send_generic_business_update_template(
                to_msisdn=msisdn,
                blob_text=message,
            )

            logger.info(
                "STAFF_NOTIFY_SENT | client_id=%s | msisdn=%s | resp=%r",
                client_id,
                msisdn,
                resp,
            )

        except Exception:
            logger.exception(
                "STAFF_NOTIFY_SEND_FAIL | client_id=%s | msisdn=%s",
                client_id,
                msisdn,
            )
