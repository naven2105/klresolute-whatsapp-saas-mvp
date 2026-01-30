from __future__ import annotations

"""
File: app/modules/inspection/service.py
Path: app/modules/inspection/service.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Inspection lifecycle operations.

Rules (LOCKED):
- Owns inspection state changes
- Commits DB transactions
- Triggers post-close actions
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.profiles.client_profile import get_client_profile

# Client-specific PDF workers (LOCKED: no refactor)
from app.clients.magen.workers.pdf_worker import (
    generate_and_send_inspection_pdf as magen_pdf_worker,
)
from app.clients.galitos.workers.pdf_worker import (
    generate_and_send_inspection_pdf as galitos_pdf_worker,
)

logger = logging.getLogger("modules.inspection")


def get_active_inspection(db: Session, *, sender: str):
    return db.execute(
        text(
            """
            SELECT inspection_id, business_msisdn
            FROM magen_inspections
            WHERE officer_msisdn = :msisdn
              AND status = 'ACTIVE'
            LIMIT 1
            """
        ),
        {"msisdn": sender},
    ).first()


def start_inspection(db: Session, *, sender: str, business_msisdn: str) -> int:
    row = db.execute(
        text(
            """
            INSERT INTO magen_inspections (officer_msisdn, business_msisdn, status)
            VALUES (:msisdn, :business, 'ACTIVE')
            RETURNING inspection_id
            """
        ),
        {"msisdn": sender, "business": business_msisdn},
    ).first()

    db.commit()

    inspection_id = row.inspection_id
    logger.info(
        "INSPECTION_STARTED | sender=%s | business=%s | id=%s",
        sender,
        business_msisdn,
        inspection_id,
    )
    return inspection_id


def close_inspection(db: Session, *, inspection_id: int, status: str):
    """
    Close inspection and trigger client-specific post-close handling.
    """

    # ----------------------------------
    # Close inspection (EXISTING BEHAVIOUR)
    # ----------------------------------
    db.execute(
        text(
            """
            UPDATE magen_inspections
            SET status = :status,
                completed_at = now()
            WHERE inspection_id = :id
            """
        ),
        {"id": inspection_id, "status": status},
    )
    db.commit()

    logger.info(
        "INSPECTION_CLOSED | id=%s | status=%s",
        inspection_id,
        status,
    )

    # ----------------------------------
    # Post-close PDF handling (NEW)
    # ----------------------------------
    inspection = db.execute(
        text(
            """
            SELECT inspection_id, business_msisdn
            FROM magen_inspections
            WHERE inspection_id = :id
            """
        ),
        {"id": inspection_id},
    ).mappings().first()

    if not inspection:
        logger.warning(
            "INSPECTION_POST_CLOSE_NO_RECORD | id=%s",
            inspection_id,
        )
        return

    profile = get_client_profile(inspection["business_msisdn"])
    if not profile:
        logger.warning(
            "INSPECTION_POST_CLOSE_NO_PROFILE | business=%s | id=%s",
            inspection["business_msisdn"],
            inspection_id,
        )
        return

    # Client-specific routing (LOCKED)
    if profile.client_code == "MAGEN":
        magen_pdf_worker(
            db=db,
            inspection_id=inspection_id,
        )

    elif profile.client_code == "GALITOS":
        galitos_pdf_worker(
            db=db,
            inspection_id=inspection_id,
        )
