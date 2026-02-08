from __future__ import annotations

"""
File: app/modules/status/reader.py
Path: app/modules/status/reader.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Read active client status banner (optional, non-blocking).

Guard Rails (LOCKED):
- STATUS must NEVER break Tier-1 routing.
- If client_status table is missing: log STATUS_TABLE_MISSING and return None.
- If table exists but no active rows: log STATUS_NONE_ACTIVE and return None.
- If query fails: rollback, log STATUS_READ_FAIL, return None.
- Always log entry + outcome with business number.
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger("modules.status.reader")


def _table_exists(db: Session, table_name: str) -> bool:
    """
    Cheap, safe existence check for a table in the public schema.
    """
    row = (
        db.execute(
            text(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = :t
                LIMIT 1
                """
            ),
            {"t": table_name},
        )
        .mappings()
        .first()
    )
    return bool(row)


def get_active_status(
    *,
    db: Session,
    business_msisdn: str,
) -> Optional[str]:
    """
    Return active status text for the business number (WhatsApp destination_number),
    or None if no status is active.

    IMPORTANT: Non-blocking. Never raises.
    """
    logger.info("STATUS_READ_ENTER | business=%s", business_msisdn)

    # Ensure we are not in an aborted transaction from earlier operations
    try:
        db.rollback()
    except Exception:
        pass

    # Guard: schema must exist
    if not _table_exists(db, "client_status"):
        logger.error("STATUS_TABLE_MISSING | business=%s | table=client_status", business_msisdn)
        return None

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
                    ORDER BY cs.updated_at DESC
                    LIMIT 1
                    """
                ),
                {"business": business_msisdn},
            )
            .mappings()
            .first()
        )

        if not row:
            logger.info("STATUS_NONE_ACTIVE | business=%s", business_msisdn)
            return None

        status_text = str(row["status_text"]).strip()
        if not status_text:
            logger.warning("STATUS_EMPTY_TEXT | business=%s", business_msisdn)
            return None

        logger.info("STATUS_ACTIVE | business=%s | chars=%s", business_msisdn, len(status_text))
        return status_text

    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        logger.exception("STATUS_READ_FAIL | business=%s | err=%s", business_msisdn, exc)
        return None
