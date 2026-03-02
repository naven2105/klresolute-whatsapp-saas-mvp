from __future__ import annotations

"""
File: app/profiles/client_profile.py
Project: KLResolute WhatsApp SaaS MVP

Sprint 21 – Final UUID Identity Model

Purpose:
Client profile resolution (DB-driven, UUID-only).

Rules:
- Identity resolved strictly via whatsapp_numbers → clients
- No client_code anywhere
- Modules via client_modules + modules
- Admins via client_admins (UUID)
- Read-only resolution only
"""

import logging
from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger("profiles.client_profile")


# -------------------------------------------------------------------
# Model
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

    if not db:
        logger.critical(
            "PROFILE_DB_NOT_PROVIDED | business=%s",
            business_msisdn,
        )
        return None

    if not business_msisdn:
        logger.error("PROFILE_LOOKUP_ABORT | reason=missing_business")
        return None

    try:
        try:
            db.rollback()
        except Exception:
            pass

        # -----------------------------------------------------------
        # Resolve client via whatsapp_numbers
        # -----------------------------------------------------------
        client_row = (
            db.execute(
                text(
                    """
                    SELECT c.client_id,
                           c.client_name
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
            "PROFILE_CLIENT_RESOLVED | business=%s | client_id=%s",
            business_msisdn,
            client_id,
        )

        # -----------------------------------------------------------
        # Modules
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

        # -----------------------------------------------------------
        # Admins
        # -----------------------------------------------------------
        admins = (
            db.execute(
                text(
                    """
                    SELECT msisdn
                    FROM client_admins
                    WHERE client_id = :client_id
                      AND is_active = TRUE
                    ORDER BY msisdn
                    """
                ),
                {"client_id": client_id},
            )
            .scalars()
            .all()
        )

        logger.info(
            "PROFILE_LOOKUP_SUCCESS | client_id=%s | admins=%s",
            client_id,
            len(admins),
        )

        return ClientProfile(
            client_id=client_id,
            client_name=client_name,
            enabled_modules=modules,
            admin_numbers=admins,
        )

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