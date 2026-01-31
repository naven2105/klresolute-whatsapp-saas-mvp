from __future__ import annotations

"""
File: app/profiles/client_profile.py
Path: app/profiles/client_profile.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Client profile resolution.

Rules (LOCKED):
- Client identity is DB-driven
- WhatsApp numbers are stored in DB, not code
- Admin allowlists are DB-driven
- Used by dispatcher, broadcast, inspections, jobs
"""

from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import text


# -------------------------------------------------------------------
# Client Profile Model
# -------------------------------------------------------------------
@dataclass(frozen=True)
class ClientProfile:
    client_id: str
    client_code: str
    enabled_modules: List[str]
    admin_numbers: List[str]


# -------------------------------------------------------------------
# Public lookup
# -------------------------------------------------------------------
def get_client_profile(
    business_msisdn: str,
    *,
    db: Optional[Session] = None,
) -> ClientProfile | None:
    """
    Resolve client profile by business WhatsApp number (DB-driven).
    """
    if not db:
        return None

    try:
        # ----------------------------------
        # Resolve client
        # ----------------------------------
        client_row = (
            db.execute(
                text(
                    """
                    SELECT c.client_id, c.client_name
                    FROM clients c
                    JOIN whatsapp_numbers w ON w.client_id = c.client_id
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

        if not client_row:
            return None

        client_id = client_row["client_id"]
        client_code = client_row["client_name"].upper()

        # ----------------------------------
        # Enabled modules
        # ----------------------------------
        modules = (
            db.execute(
                text(
                    """
                    SELECT m.module_code
                    FROM client_modules cm
                    JOIN modules m ON m.id = cm.module_id
                    WHERE cm.client_id = :client_id
                      AND cm.is_enabled = TRUE
                    """
                ),
                {"client_id": client_id},
            )
            .scalars()
            .all()
        )

        # ----------------------------------
        # Admin numbers
        # ----------------------------------
        admins = (
            db.execute(
                text(
                    """
                    SELECT admin_number
                    FROM client_admins
                    WHERE client_id = :client_id
                      AND is_active = TRUE
                    """
                ),
                {"client_id": client_id},
            )
            .scalars()
            .all()
        )

        return ClientProfile(
            client_id=client_id,
            client_code=client_code,
            enabled_modules=modules,
            admin_numbers=admins,
        )

    except Exception:
        return None
