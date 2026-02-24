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
- Handle fallback logic
- Central error handling
- No payload parsing
"""

import logging

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.inbound_dispatcher import dispatch
from app.handlers.tier1_router import handle_client_command
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

    # ✅ Guaranteed-visible dispatch markers (stdout + warning)
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

    if not handled:
        body = (
            msg.get("text", {}).get("body", "").strip()
            if msg.get("type") == "text"
            else ""
        )

        logger.warning(
            "FALLBACK_EVAL | sender=%s | body=%r",
            sender,
            body,
        )

        if body.upper() not in ("YES", "NO"):
            client_id_uuid = _resolve_uuid_client_id(
                db,
                business_msisdn=business_msisdn,
            )

            if client_id_uuid is not None:
                handle_client_command(
                    db=db,
                    sender_number=sender,
                    message_text=body,
                    msg=msg,
                    resolved_client_id=client_id_uuid,
                    resolved_business_number=business_msisdn,
                )