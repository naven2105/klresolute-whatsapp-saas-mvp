from __future__ import annotations

"""
File: app/modules/status/admin_handler.py
Path: app/modules/status/admin_handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Handle ADMIN-only STATUS / ANNOUNCEMENT commands.

Command format (LOCKED):
STATUS: <message>

Rules (LOCKED):
- Admins only
- One active status per client
- New status overwrites existing one
- No customer delivery here (read-only elsewhere)
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.utils.admin import is_admin_message

logger = logging.getLogger("modules.status.admin_handler")


def handle_status_command(
    *,
    db: Session,
    sender: str,
    message_text: str,
    business_msisdn: str,
) -> bool:
    """
    Returns True if message was handled (admin STATUS command).
    Returns False if message is not a STATUS command.
    """

    # ----------------------------------
    # Guard: command format
    # ----------------------------------
    if not message_text:
        return False

    raw = message_text.strip()
    if not raw.upper().startswith("STATUS:"):
        return False

    # ----------------------------------
    # Guard: admin only
    # ----------------------------------
    if not is_admin_message(
        db=db,
        sender=sender,
        business_msisdn=business_msisdn,
    ):
        logger.warning(
            "STATUS_REJECTED_NON_ADMIN | sender=%s | business=%s",
            sender,
            business_msisdn,
        )
        return True  # consumed but rejected

    status_text = raw.split(":", 1)[1].strip()

    if not status_text:
        logger.error(
            "STATUS_REJECTED_EMPTY | sender=%s | business=%s",
            sender,
            business_msisdn,
        )
        return True

    # ----------------------------------
    # Resolve client UUID
    # ----------------------------------
    row = (
        db.execute(
            text(
                """
                SELECT c.client_id
                FROM whatsapp_numbers w
                JOIN clients c ON c.client_id = w.client_id
                WHERE w.destination_number = :business
                  AND w.status = 'active'
                LIMIT 1
                """
            ),
            {"business": business_msisdn},
        )
        .mappings()
        .first()
    )

    if not row:
        logger.error(
            "STATUS_CLIENT_RESOLUTION_FAIL | business=%s | sender=%s",
            business_msisdn,
            sender,
        )
        return True

    client_id = str(row["client_id"])

    # ----------------------------------
    # Upsert status (single active row)
    # ----------------------------------
    try:
        db.execute(
            text(
                """
                INSERT INTO client_status (
                    client_id,
                    status_text,
                    is_active,
                    created_at
                )
                VALUES (
                    :client_id,
                    :status_text,
                    TRUE,
                    now()
                )
                ON CONFLICT (client_id)
                DO UPDATE SET
                    status_text = EXCLUDED.status_text,
                    is_active = TRUE,
                    created_at = now(),
                    expires_at = NULL
                """
            ),
            {
                "client_id": client_id,
                "status_text": status_text,
            },
        )
        db.commit()

        logger.info(
            "STATUS_SET_OK | client_id=%s | sender=%s",
            client_id,
            sender,
        )

    except Exception as exc:
        db.rollback()
        logger.exception(
            "STATUS_SET_FAIL | client_id=%s | sender=%s | err=%s",
            client_id,
            sender,
            exc,
        )
        return True

    # ----------------------------------
    # Confirm to admin
    # ----------------------------------
    try:
        from app.outbound.factory import get_meta_client

        meta = get_meta_client(business_msisdn=business_msisdn)
        meta.send_session_message(
            to_msisdn=sender,
            text="✅ Status updated. Customers will see this on their next interaction.",
        )
    except Exception:
        logger.exception(
            "STATUS_ADMIN_CONFIRM_FAIL | sender=%s | business=%s",
            sender,
            business_msisdn,
        )

    return True
