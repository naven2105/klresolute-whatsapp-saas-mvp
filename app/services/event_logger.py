"""
File: app/services/event_logger.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Centralised event logging.
Guarantees event_logs.client_id is always populated.
"""

from __future__ import annotations

import uuid
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models import Client, EventLog


def _get_or_create_client(db: Session, msisdn: str) -> Client:
    """
    Resolve client by phone number.
    Creates client row if it does not exist.
    """

    client = (
        db.execute(
            select(Client).where(Client.client_number == msisdn)
        )
        .scalars()
        .one_or_none()
    )

    if client:
        return client

    client = Client(
        client_id=uuid.uuid4(),
        client_number=msisdn,
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


def log_event(
    *,
    db: Session,
    sender_number: str,
    event_type: str,
    event_detail: str | None = None,
    conversation_id: uuid.UUID | None = None,
    message_id: uuid.UUID | None = None,
) -> None:
    """
    Persist an event log with guaranteed client_id.
    """

    client = _get_or_create_client(db, sender_number)

    event = EventLog(
        event_id=uuid.uuid4(),
        client_id=client.client_id,
        conversation_id=conversation_id,
        message_id=message_id,
        event_type=event_type,
        event_detail=event_detail,
    )

    db.add(event)
    db.commit()
