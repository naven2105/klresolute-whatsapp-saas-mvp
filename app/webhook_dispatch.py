from __future__ import annotations

"""
File: app/webhook_dispatch.py
Path: app/webhook_dispatch.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Tenant resolution + routing dispatch and fallback handling.

Rules:
- Tenant resolution
- Route to client module
- Central error handling
- No business fallback logic
"""

import logging

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.inbound_dispatcher import dispatch
from app.clients.magen.inspection.auto_close_worker import auto_close_expired_inspections

logger = logging.getLogger("webhooks")


def _resolve_uuid_client_id(
    db: Session,
    *,
    business_msisdn: str,
) -> str | None:
    """
    UUID-only identity resolution (post-migration).
    """
    try:
        row = (
            db.execute(
                text(
                    """
                    SELECT client_id
                    FROM whatsapp_numbers
                    WHERE destination_number = :business
                      AND status = 'active'
                    LIMIT 1
                    """
                ),
                {"business": business_msisdn},
            )
            .mappings()
            .first()
        )

        if not row or not row.get("client_id"):
            logger.error(
                "CLIENT_ID_UUID_NOT_FOUND | business=%s",
                business_msisdn,
            )
            return None

        logger.info(
            "CLIENT_ID_UUID_RESOLVED | business=%s | client_id=%s",
            business_msisdn,
            row["client_id"],
        )

        return str(row["client_id"])

    except Exception:
        logger.exception(
            "CLIENT_ID_UUID_LOOKUP_FAIL | business=%s",
            business_msisdn,
        )
        return None


def dispatch_and_fallback(
    *,
    db: Session,
    msg: dict,
    sender: str,
    business_msisdn: str,
) -> None:
    try:
        auto_close_expired_inspections(db)
        logger.info("AUTO_CLOSE_CHECK_DONE")
    except Exception:
        logger.exception("AUTO_CLOSE_FAIL")

    print(
        f"🚀 DISPATCH_CALL | sender={sender} | business={business_msisdn} | type={msg.get('type')}"
    )
    logger.warning(
        "DISPATCH_CALL | sender=%s | business=%s | msg_type=%s",
        sender,
        business_msisdn,
        msg.get("type"),
    )

    handled = dispatch(
        db=db,
        msg=msg,
        sender=sender,
        business_msisdn=business_msisdn,
    )

    print(f"🏁 DISPATCH_RETURN | handled={handled} | sender={sender}")
    logger.warning(
        "DISPATCH_RETURN | handled=%s | sender=%s | business=%s",
        handled,
        sender,
        business_msisdn,
    )

    # No global fallback.
    # Tenant dispatchers are fully responsible for handling.