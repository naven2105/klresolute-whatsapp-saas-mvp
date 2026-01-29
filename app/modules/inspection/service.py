from __future__ import annotations

"""
File: app/modules/inspection/service.py
Path: app/modules/inspection/service.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Inspection lifecycle operations.
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger("modules.inspection")


def get_active_inspection(db: Session, *, sender: str):
    return db.execute(
        text(
            """
            SELECT inspection_id
            FROM magen_inspections
            WHERE officer_msisdn = :msisdn
              AND status = 'ACTIVE'
            LIMIT 1
            """
        ),
        {"msisdn": sender},
    ).first()


def start_inspection(db: Session, *, sender: str) -> int:
    row = db.execute(
        text(
            """
            INSERT INTO magen_inspections (officer_msisdn, status)
            VALUES (:msisdn, 'ACTIVE')
            RETURNING inspection_id
            """
        ),
        {"msisdn": sender},
    ).first()

    db.commit()

    inspection_id = row.inspection_id
    logger.info(
        "INSPECTION_STARTED | sender=%s | id=%s",
        sender,
        inspection_id,
    )
    return inspection_id


def close_inspection(db: Session, *, inspection_id: int, status: str):
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
