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

from sqlalchemy.orm import Session
from sqlalchemy import text


def is_admin_message(
    *,
    db: Session,
    sender: str,
    business_msisdn: str,
) -> bool:
    """
    Returns True if sender is an active admin for the given client.
    Fail-closed by default.
    """

    row = db.execute(
        text(
            """
            SELECT 1
            FROM client_admins
            WHERE msisdn = :msisdn
              AND client_code = :client
              AND is_active = TRUE
            LIMIT 1
            """
        ),
        {
            "msisdn": sender,
            "client": business_msisdn,
        },
    ).first()

    return row is not None
