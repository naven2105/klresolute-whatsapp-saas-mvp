from __future__ import annotations

"""
File: app/clients/magen/staff_repo.py
Path: app/clients/magen/staff_repo.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Staff lookup for Magen Security inspections.

Responsibilities (LOCKED):
- Validate whether a sender is an active Magen security officer

Notes:
- Read-only DB access
- No messaging
- No inspection lifecycle logic
"""

from sqlalchemy.orm import Session
from sqlalchemy import text


def is_active_staff(db: Session, *, msisdn: str) -> bool:
    row = db.execute(
        text(
            """
            SELECT 1
            FROM magen_staff
            WHERE msisdn = :msisdn
              AND is_active = TRUE
            LIMIT 1
            """
        ),
        {"msisdn": msisdn},
    ).first()

    return bool(row)
