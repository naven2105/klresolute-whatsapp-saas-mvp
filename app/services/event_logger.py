"""
File: app/services/event_logger.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Centralised event logging.

Design:
- Caller MUST supply client_id
- No inference from phone numbers
- No DB lookups or side effects
"""

from __future__ import annotations

import uuid
from sqlalchemy.orm import Session

from app.models import EventLog


def log_event(
    *,
    db: Session,
    client_id: uuid.UUID,
    event_type: str,
    event_detail: str | None = None,
    conversation_id: uuid.UUID | None = None,
    message_id: uuid.UUID | None = None,
) -> None:
    """
    Persist an event log.

    Contract:
    - client_id is mandatory
    - caller is responsible for resolving it correctly
    """

    event = EventLog(
        event_id=uuid.uuid4(),
        client_id=client_id,
        conversation_id=conversation_id,
        message_id=message_id,
        event_type=event_type,
        event_detail=event_detail,
    )

    db.add(event)
    db.commit()
