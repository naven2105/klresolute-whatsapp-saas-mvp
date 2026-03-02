from __future__ import annotations

"""
File: app/clients/galitos/handlers/inspection_handler.py
Project: KLResolute WhatsApp SaaS MVP

Sprint 21 – Tenant Isolation

Purpose:
Galitos inspection handler (tenant-scoped).

Rules:
- UUID-only identity
- Staff-only access
- No client_code usage
- No cross-tenant logic
"""

import logging
from sqlalchemy.orm import Session

from app.services.staff_resolver import resolve_staff

logger = logging.getLogger("clients.galitos.inspection")


GALITOS_CLIENT_ID = "906a5084-1add-4b7a-bda0-90b462c9b8a9"


def handle_inspection(
    *,
    db: Session,
    client_id: str,
    sender_msisdn: str,
    message_text: str,
) -> bool:

    if client_id != GALITOS_CLIENT_ID:
        return False

    # -------------------------------------------------
    # Staff gate
    # -------------------------------------------------
    is_staff = resolve_staff(
        db=db,
        client_id=client_id,
        sender_msisdn=sender_msisdn,
    )

    if not is_staff:
        logger.info(
            "GALITOS_INSPECTION_REJECTED | client_id=%s | sender=%s",
            client_id,
            sender_msisdn,
        )
        return False

    # Existing inspection logic continues here

    return True