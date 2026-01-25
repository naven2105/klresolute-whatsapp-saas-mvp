from __future__ import annotations

"""
File: app/clients/magen/inbound.py
Purpose:
Entry point for Magen inbound dispatch.
"""

from sqlalchemy.orm import Session
from app.clients.magen.customer_commands import handle_magen_customer


def handle_inbound(
    *,
    db: Session,
    msg: dict,
    sender: str,
    business_msisdn: str,
) -> bool:
    return handle_magen_customer(
        db=db,
        business_msisdn=business_msisdn,
        sender=sender,
    )
