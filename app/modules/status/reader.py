from __future__ import annotations

"""
File: app/modules/status/reader.py
Path: app/modules/status/reader.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Read active client STATUS / ANNOUNCEMENT for display to customers.

Rules (LOCKED):
- Read-only
- No writes
- Expiry checked at read time
- Fail silent (status is optional)
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger("modules.status.reader")


def get_active_status(
    *,
    db: Session,
    business_msisdn: str,
) -> str | None:
    """
    Returns active status text for a client, or None if not present / expired.
    """

    try:
        row = (
            db.execute(
                text(
                    """
                    SELECT cs.status_text
                    FROM client_status cs
                    JOIN whatsapp_numbers w ON w.client_id = cs.client_id
                    WHERE w.destination_number = :business
                      AND w.status = 'active'
                      AND cs.is_active = TRUE
                      AND (
                            cs.expires_at IS NULL
                            OR cs.expires_at > now()
                          )
                    LIMIT 1
                    """
                ),
                {"business": business_msisdn},
            )
            .mappings()
            .first()
        )

        if not row:
            logger.debug(
                "STATUS_NOT_PRESENT | business=%s",
                business_msisdn,
            )
            return None

        logger.info(
            "STATUS_READ_OK | business=%s",
            business_msisdn,
        )
        return str(row["status_text"])

    except Exception as exc:
        logger.exception(
            "STATUS_READ_FAIL | business=%s | err=%s",
            business_msisdn,
            exc,
        )
        return None
