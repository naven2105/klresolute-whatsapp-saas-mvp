from __future__ import annotations

"""
File: app/modules/specials/service.py
Project: KLResolute WhatsApp SaaS MVP

ROLE (EXPLICIT & LOCKED):
Customer-facing SPECIALS retrieval service.

RESPONSIBILITY:
- Retrieve latest SPECIAL from specials table
- Send image + caption to customer
- Never raise
- Never break caller
- Fail safe with logging

SOURCE OF TRUTH:
- specials table (client_id UUID based)
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
) -> bool:
    """
    Returns:
        True  → special sent
        False → no special found
    """

    logger.info(
        "SPECIALS_SERVICE_ENTER | client_uuid=%s | to=%s",
        client_uuid,
        to_msisdn,
    )

    if not client_uuid:
        logger.error("SPECIALS_SERVICE_ABORT | reason=missing_client_uuid")
        return False

    try:
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
                "SPECIALS_SERVICE_NONE_FOUND | client_uuid=%s",
                client_uuid,
            )
            return False

        media_id = row["media_id"]
        caption = row["caption"]

        logger.info(
            "SPECIALS_SERVICE_FOUND | client_uuid=%s | media_id=%s",
            client_uuid,
            media_id,
        )

        meta = get_meta_client()

        meta.send_image_message(
            to_msisdn=to_msisdn,
            media_id=media_id,
            caption=caption,
        )

        logger.info(
            "SPECIALS_SERVICE_SENT | to=%s | media_id=%s",
            to_msisdn,
            media_id,
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
