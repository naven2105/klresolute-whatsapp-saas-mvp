from __future__ import annotations

"""
File: app/modules/broadcast/repo.py
Path: app/modules/broadcast/repo.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Audience lookup for broadcast messages.
"""

from sqlalchemy.orm import Session
from sqlalchemy import text


def get_active_staff_numbers(db: Session, *, client_code: str) -> list[str]:
    """
    Phase-1: broadcast to active staff only.
    """
    rows = db.execute(
        text(
            """
            SELECT msisdn
            FROM staff_registry
            WHERE client_code = :client
              AND is_active = TRUE
            """
        ),
        {"client": client_code},
    ).fetchall()

    return [r.msisdn for r in rows]
