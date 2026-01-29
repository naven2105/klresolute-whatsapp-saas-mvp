from __future__ import annotations

"""
File: app/modules/vehicle_inspection/handler.py
Path: app/modules/vehicle_inspection/handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Stub handler for Vehicle Inspection module.

Responsibilities (LOCKED):
- Claim vehicle inspection messages (future)
- Return False for now so inspection module continues to work
- NO DB writes
- NO outbound messaging
"""

import logging
from sqlalchemy.orm import Session

logger = logging.getLogger("module.vehicle_inspection")


def handle(
    *,
    db: Session,
    msg: dict,
    sender: str,
    business_msisdn: str,
) -> bool:
    """
    Vehicle Inspection module stub.
    """

    # Not implemented yet
    return False
