from __future__ import annotations

"""
File: app/handlers/inspection_handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Handle staff inspections (shared engine for all clients).

Rules (LOCKED):
- One inspection engine
- Staff-only access
- Client-driven behaviour
- No client-specific branching here
"""

import logging
from sqlalchemy.orm import Session

from app.services.staff_resolver import resolve_staff
from app.config import get_client_profile

logger = logging.getLogger("inspection_handler")


def handle_inspection(
    *,
    db: Session,
    client_code: str,
    sender_msisdn: str,
    message_text: str,
) -> bool:
    """
    Entry point for inspection handling.

    Returns:
    - True if message was consumed by inspection flow
    - False if inspection is not applicable
    """

    profile = get_client_profile(client_code)
    if not profile:
        return False

    if not profile.inspections_enabled:
        return False

    # -------------------------------------------------
    # Staff gate (EARLY EXIT)
    # -------------------------------------------------
    is_staff = resolve_staff(
        db=db,
        client_code=client_code,
        sender_msisdn=sender_msisdn,
    )

    if not is_staff:
        logger.info(
            "Inspection rejected (non-staff): client=%s msisdn=%s",
            client_code,
            sender_msisdn,
        )
        return False

    # -------------------------------------------------
    # Existing inspection engine continues here
    # (NO changes below this line)
    # -------------------------------------------------

    # Example placeholder:
    # process_inspection_message(db=db, sender_msisdn=sender_msisdn, text=message_text)

    return True
