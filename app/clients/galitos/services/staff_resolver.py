from __future__ import annotations

"""
File: app/clients/galitos/services/staff_resolver.py
Project: KLResolute WhatsApp SaaS MVP

Sprint 21 – Tenant Isolation

Purpose:
Galitos staff resolver (tenant-scoped).

Rules:
- UUID identity enforced at caller
- Queries galitos_staff only
- Read-only
"""

from sqlalchemy.orm import Session
from sqlalchemy import text


def resolve_staff(
    *,
    db: Session,
    sender_msisdn: str,
) -> bool:
    """
    Returns True if sender is active Galitos staff.
    """

    result = db.execute(
        text(
            """
            SELECT 1
            FROM galitos_staff
            WHERE msisdn = :msisdn
              AND is_active = TRUE
            LIMIT 1
            """
        ),
        {"msisdn": sender_msisdn},
    ).first()

    return result is not None