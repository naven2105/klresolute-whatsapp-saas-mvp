from __future__ import annotations

"""
File: app/modules/specials/service.py
Project: KLResolute WhatsApp SaaS MVP

ROLE:
Customer-facing SPECIALS retrieval service.

GUARDS:
- Never raise
- Never break caller
- Log clearly
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.outbound.factory import get_meta_client

logger = logging.getLogger("specials.service")


def _resolve_client_uuid(
    db: Session,
    *,
    klresolute_client_id: str,
) -> str | None:
    """
    Convert INTEGER klresolute_client_id -> UUID client_id
    """
    try:
        row = (
            db.execute(
                text(
                    """
                    SELECT client_id
                    FROM whatsapp_numbers
                    WHERE klresolute_client_id = :cid
                      AND status = 'active'
                    LIMIT 1
                    """
                ),
                {"cid": int(klresolute_client_id)},
            )
            .mappings()
            .first()
        )

        if not row:
            logger.error(
                "SPECIALS_UUID_NOT_FOUND | klresolute_client_id=%s",
                klresolute_client_id,
            )
            return None

        return str(row["client_id"])

    except Exception as exc:
        logger.exception(
            "SPECIALS_UUID_RESOLUTION_FAIL | klresolute_client_id=%s | err=%s",
            klresolute_client_id,
            exc,
        )
        return None


def send_latest_special_to_customer(
    *,
    db: Session,
    client_uuid: str,
    to_msisdn: str,
) -> bool:
    """
    Sends latest SPECIAL to customer.

    Returns:
    - True  -> special sent
    - False -> no special found
    """

    try:
        # ----------------------------------------
        # Resolve UUID from integer ID
        # ----------------------------------------
        resolved_uuid = _resolve_client_uuid(
            db,
            klresolute_client_id=client_uuid,
        )

        if not resolved_uuid:
            return False

        # ----------------------------------------
        # Fetch latest special
        # ----------------------------------------
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
                {"client_id": resolved_uuid},
            )
            .mappings()
            .first()
        )

        if not row:
            logger.info(
                "SPECIALS_NONE_FOUND | client_uuid=%s",
                resolved_uuid,
            )
            return False

        # ----------------------------------------
        # Send image
        # ----------------------------------------
        meta = get_meta_client()

        meta.send_image_message(
            to_msisdn=to_msisdn,
            media_id=row["media_id"],
            caption=row["caption"],
        )

        logger.info(
            "SPECIALS_SENT | to=%s | client_uuid=%s",
            to_msisdn,
            resolved_uuid,
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
