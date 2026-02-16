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
- Used by dispatcher, special, inspections, jobs
"""

import logging
from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger("profiles.client_profile")

# -------------------------------------------------------------------
# Static text (import guard)
# -------------------------------------------------------------------
ABOUT_TEXT = (
    "This business uses an automated WhatsApp assistant. "
    "Reply with menu options or STOP to opt out."
)

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
    if not db:
        logger.error(
            "PROFILE_DB_NOT_PROVIDED | business=%s",
            business_msisdn,
        )
        return None

    try:
        try:
            db.rollback()
        except Exception:
            pass

        client_row = (
            db.execute(
                text(
                    """
                    SELECT c.client_id, c.client_name
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

        if not client_row:
            logger.error(
                "PROFILE_CLIENT_NOT_FOUND | business=%s",
                business_msisdn,
            )
            return None

        client_id = str(client_row["client_id"])
        client_code = str(client_row["client_name"]).upper()

        modules = (
            db.execute(
                text(
                    """
                    SELECT m.module_code
                    FROM client_modules cm
                    JOIN modules m ON m.id = cm.module_id
                    WHERE cm.client_id = :client_id
                      AND cm.is_enabled = TRUE
                      AND m.is_active = TRUE
                    ORDER BY m.module_code
                    """
                ),
                {"client_id": client_id},
            )
            .scalars()
            .all()
        )

        if not modules:
            logger.warning(
                "PROFILE_NO_MODULES_ENABLED | business=%s | client_code=%s",
                business_msisdn,
                client_code,
            )

        admins = (
            db.execute(
                text(
                    """
                    SELECT msisdn
                    FROM client_admins
                    WHERE client_code = :client_code
                      AND is_active = TRUE
                    ORDER BY msisdn
                    """
                ),
                {"client_code": client_code},
            )
            .scalars()
            .all()
        )

        logger.info(
            "PROFILE_RESOLVED | business=%s | client_id=%s | client_code=%s | modules=%s | admins=%s",
            business_msisdn,
            client_id,
            client_code,
            ",".join(modules) if modules else "-",
            len(admins),
        )

        return ClientProfile(
            client_id=client_id,
            client_code=client_code,
            enabled_modules=modules,
            admin_numbers=admins,
        )

    except Exception:
        try:
            db.rollback()
        except Exception:
            pass

        logger.exception(
            "PROFILE_RESOLUTION_FAILED | business=%s",
            business_msisdn,
        )
        return None
