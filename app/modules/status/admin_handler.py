from __future__ import annotations

"""
File: app/modules/status/admin_handler.py
Path: app/modules/status/admin_handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Admin-only Status / Announcement writer.

Responsibility (SINGLE):
- Allow admins to set or clear a client status message.

Rules:
- Admin-only
- DB-driven client resolution
- Fail closed
- No customer routing
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.utils.admin import is_admin_message

logger = logging.getLogger("modules.status.admin_handler")


# -------------------------------------------------
# Public entry
# -------------------------------------------------

def handle_status_command(
    *,
    db: Session,
    sender: str,
    business_msisdn: str,
    message_text: str,
) -> bool:
    """
    Handles admin STATUS commands.

    Supported:
    - STATUS: <text>
    - STATUS OFF
    """

    upper = (message_text or "").strip().upper()

    # ----------------------------------
    # Guard: admin only
    # ----------------------------------
    if not is_admin_message(
        db=db,
        sender=sender,
        business_msisdn=business_msisdn,
    ):
        logger.info(
            "STATUS_REJECTED | reason=not_admin | sender=%s | business=%s",
            sender,
            business_msisdn,
        )
        return False

    # ----------------------------------
    # Resolve client_id (INTEGER MVP)
    # ----------------------------------
    row = (
        db.execute(
            text(
                """
                SELECT klresolute_client_id
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

    if not row or row["klresolute_client_id"] is None:
        logger.error(
            "STATUS_BLOCKED | reason=client_not_resolved | business=%s",
            business_msisdn,
        )
        return True

    client_id = int(row["klresolute_client_id"])

    # ----------------------------------
    # STATUS OFF
    # ----------------------------------
    if upper == "STATUS OFF":
        db.execute(
            text(
                """
                UPDATE client_status
                SET is_active = FALSE
                WHERE client_id = :client_id
                  AND is_active = TRUE
                """
            ),
            {"client_id": client_id},
        )
        db.commit()

        logger.info(
            "STATUS_CLEARED | client_id=%s | by=%s",
            client_id,
            sender,
        )
        return True

    # ----------------------------------
    # STATUS SET
    # ----------------------------------
    if upper.startswith("STATUS:"):
        status_text = message_text.split(":", 1)[1].strip()

        if not status_text:
            logger.warning(
                "STATUS_EMPTY | client_id=%s | sender=%s",
                client_id,
                sender,
            )
            return True

        # deactivate previous
        db.execute(
            text(
                """
                UPDATE client_status
                SET is_active = FALSE
                WHERE client_id = :client_id
                  AND is_active = TRUE
                """
            ),
            {"client_id": client_id},
        )

        # insert new
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
                """
            ),
            {
                "client_id": client_id,
                "status_text": status_text,
            },
        )
        db.commit()

        logger.info(
            "STATUS_SET | client_id=%s | by=%s | text=%r",
            client_id,
            sender,
            status_text,
        )
        return True

    return False
