from __future__ import annotations

"""
File: app/utils/admin.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Admin resolution utilities.

Rules (LOCKED):
- Fail closed
- DB-driven
- No hardcoded admin numbers
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger("utils.admin")


def is_admin_message(
    *,
    db: Session,
    sender: str,
    business_msisdn: str,
) -> bool:
    """
    Returns True if sender is an active admin for the given business.
    Fail-closed by default.
    """

    # ----------------------------------
    # Resolve client_code from business_msisdn
    # ----------------------------------
    row = (
        db.execute(
            text(
                """
                SELECT c.client_name
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
            "ADMIN_CHECK_BLOCKED | reason=client_not_resolved | business=%s | sender=%s",
            business_msisdn,
            sender,
        )
        return False

    client_code = str(row["client_name"]).upper()

    # ----------------------------------
    # Check admin allowlist
    # ----------------------------------
    admin_row = (
        db.execute(
            text(
                """
                SELECT 1
                FROM client_admins
                WHERE msisdn = :msisdn
                  AND client_code = :client_code
                  AND is_active = TRUE
                LIMIT 1
                """
            ),
            {
                "msisdn": sender,
                "client_code": client_code,
            },
        )
        .first()
    )

    if not admin_row:
        logger.info(
            "ADMIN_CHECK_FALSE | business=%s | client_code=%s | sender=%s",
            business_msisdn,
            client_code,
            sender,
        )
        return False

    logger.info(
        "ADMIN_CHECK_TRUE | business=%s | client_code=%s | sender=%s",
        business_msisdn,
        client_code,
        sender,
    )
    return True
