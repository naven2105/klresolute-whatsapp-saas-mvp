from __future__ import annotations

"""
File: app/profiles/client_profile.py
Path: app/profiles/client_profile.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Client profile resolution (DB-driven).

LOCKED RULES:
- Client identity resolved strictly via whatsapp_numbers → clients
- No hard-coded business numbers
- Modules resolved via client_modules + modules
- Admins resolved via client_admins
- No business logic
- No outbound messaging
- Read-only resolution only
- Must log WHY resolution fails
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
    client_name: str
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

    logger.info(
        "PROFILE_LOOKUP_START | business=%s",
        business_msisdn,
    )

    # ---------------------------------------------------------------
    # Guard: DB must be provided
    # ---------------------------------------------------------------
    if not db:
        logger.critical(
            "PROFILE_DB_NOT_PROVIDED | business=%s",
            business_msisdn,
        )
        return None

    # ---------------------------------------------------------------
    # Guard: business number required
    # ---------------------------------------------------------------
    if not business_msisdn:
        logger.error("PROFILE_LOOKUP_ABORT | reason=missing_business")
        return None

    try:
        # Defensive rollback guard
        try:
            db.rollback()
        except Exception:
            logger.warning("PROFILE_ROLLBACK_SKIP")

        # -----------------------------------------------------------
        # Resolve client via whatsapp_numbers
        # -----------------------------------------------------------
        client_row = (
            db.execute(
                text(
                    """
                    SELECT c.client_id,
                           c.client_name,
                           w.destination_number
                    FROM whatsapp_numbers w
                    JOIN clients c
                      ON c.client_id = w.client_id
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
        client_name = str(client_row["client_name"])

        logger.info(
            "PROFILE_CLIENT_RESOLVED | business=%s | client_id=%s | client_name=%s",
            business_msisdn,
            client_id,
            client_name,
        )

        # -----------------------------------------------------------
        # Resolve enabled modules
        # -----------------------------------------------------------
        modules = (
            db.execute(
                text(
                    """
                    SELECT m.module_code
                    FROM client_modules cm
                    JOIN modules m
                      ON m.id = cm.module_id
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
                "PROFILE_NO_MODULES_ENABLED | client_id=%s | client_name=%s",
                client_id,
                client_name,
            )
        else:
            logger.info(
                "PROFILE_MODULES_RESOLVED | client_id=%s | modules=%s",
                client_id,
                ",".join(modules),
            )

        # -----------------------------------------------------------
        # Resolve admin numbers
        # NOTE: client_admins still keyed by client_name
        # -----------------------------------------------------------
        admins = (
            db.execute(
                text(
                    """
                    SELECT msisdn
                    FROM client_admins
                    WHERE client_code = :client_name
                      AND is_active = TRUE
                    ORDER BY msisdn
                    """
                ),
                {"client_name": client_name},
            )
            .scalars()
            .all()
        )

        logger.info(
            "PROFILE_ADMINS_RESOLVED | client_id=%s | admin_count=%s",
            client_id,
            len(admins),
        )

        # -----------------------------------------------------------
        # Final profile object
        # -----------------------------------------------------------
        profile = ClientProfile(
            client_id=client_id,
            client_name=client_name,
            enabled_modules=modules,
            admin_numbers=admins,
        )

        logger.info(
            "PROFILE_LOOKUP_SUCCESS | client_id=%s | business=%s",
            client_id,
            business_msisdn,
        )

        return profile

    except Exception:
        try:
            db.rollback()
        except Exception:
            pass

        logger.exception(
            "PROFILE_LOOKUP_FATAL | business=%s",
            business_msisdn,
        )
        return None
