from __future__ import annotations

"""
File: app/clients/magen/announcements/service.py
Path: app/modules/announcements/service.py
Project: KLResolute WhatsApp SaaS MVP

Sprint: Full UUID Identity Migration

ROLE:
Customer-facing ANNOUNCEMENTS retrieval service.

GUARDS:
- Never raise
- Never break caller
- UUID-only identity
- Defensive rollback protection
- Business-scoped Meta sender identity
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.outbound.factory import get_meta_client

logger = logging.getLogger("announcements.service")


def send_latest_announcement_to_customer(
    *,
    db: Session,
    client_uuid: str,
    to_msisdn: str,
    business_msisdn: str,
) -> bool:
    """
    Sends latest ANNOUNCEMENT to customer.

    Returns:
    - True  -> announcement sent
    - False -> no announcement found
    """

    try:
        try:
            db.rollback()
        except Exception:
            logger.exception(
                "ANNOUNCEMENTS_DB_RESET_FAIL | client_uuid=%s",
                client_uuid,
            )

        row = (
            db.execute(
                text(
                    """
                    SELECT media_id, caption
                    FROM announcements
                    WHERE client_id = :client_id
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                ),
                {"client_id": client_uuid},
            )
            .mappings()
            .first()
        )

        if not row:
            logger.info(
                "ANNOUNCEMENTS_NONE_FOUND | client_uuid=%s",
                client_uuid,
            )
            return False

        meta = get_meta_client(
            db=db,
            business_msisdn=business_msisdn,
        )

        meta.send_image_message(
            to_msisdn=to_msisdn,
            media_id=row["media_id"],
            caption=row["caption"],
        )

        logger.info(
            "ANNOUNCEMENTS_SENT | to=%s | client_uuid=%s | business=%s",
            to_msisdn,
            client_uuid,
            business_msisdn,
        )

        return True

    except Exception as exc:
        logger.exception(
            "ANNOUNCEMENTS_SERVICE_FAIL | client_uuid=%s | to=%s | err=%s",
            client_uuid,
            to_msisdn,
            exc,
        )
        return False
