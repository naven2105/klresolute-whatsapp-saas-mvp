from __future__ import annotations

"""
File: app/modules/specials/service.py
Path: app/modules/specials/service.py
Project: KLResolute WhatsApp SaaS MVP

Sprint: Full UUID Identity Migration

ROLE:
Customer-facing SPECIALS retrieval service.

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

logger = logging.getLogger("specials.service")


def send_latest_special_to_customer(
    *,
    db: Session,
    client_uuid: str,
    to_msisdn: str,
    business_msisdn: str,
) -> bool:
    """
    Sends latest SPECIAL to customer.

    Returns:
    - True  -> special sent
    - False -> no special found
    """

    try:
        try:
            db.rollback()
        except Exception:
            logger.exception(
                "SPECIALS_DB_RESET_FAIL | client_uuid=%s",
                client_uuid,
            )

        row = (
            db.execute(
                text(
                    """
                    SELECT media_id, caption
                    FROM specials
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
                "SPECIALS_NONE_FOUND | client_uuid=%s",
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
            "SPECIALS_SENT | to=%s | client_uuid=%s | business=%s",
            to_msisdn,
            client_uuid,
            business_msisdn,
        )

        return True

    except Exception as exc:
        logger.exception(
            "SPECIALS_SERVICE_FAIL | client_uuid=%s | to=%s | err=%s",
            client_uuid,
            to_msisdn,
            exc,
        )
        return False
