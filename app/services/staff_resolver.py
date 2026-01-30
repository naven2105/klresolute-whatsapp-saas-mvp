from __future__ import annotations

"""
File: app/services/staff_resolver.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Resolve whether a sender is a staff member for a given client.

Rules (LOCKED):
- Read-only DB access
- Client-driven (via app.config)
- No inspection logic
- No messaging logic
"""

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.config import get_client_profile


def resolve_staff(
    *,
    db: Session,
    client_code: str,
    sender_msisdn: str,
) -> bool:
    """
    Returns True if sender is an active staff member for the client.
    Returns False otherwise (including unknown client).
    """

    profile = get_client_profile(client_code)
    if not profile:
        return False

    staff_table = profile.staff_table

    result = db.execute(
        text(
            f"""
            SELECT 1
            FROM {staff_table}
            WHERE msisdn = :msisdn
              AND is_active = TRUE
            LIMIT 1
            """
        ),
        {"msisdn": sender_msisdn},
    ).first()

    return result is not None
