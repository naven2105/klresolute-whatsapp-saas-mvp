"""
File: app/services/event_logger.py

Purpose:
Centralised event logging into event_logs table.
Uses existing SQLAlchemy SessionLocal.
"""

from datetime import datetime
from app.db import SessionLocal
from app.models import EventLog


def log_event(
    *,
    db=None,
    sender_number: str | None = None,
    event_type: str,
    event_detail: str,
) -> None:
    """
    Write a single event_logs row.
    If db session is provided, reuse it.
    Otherwise create a short-lived session.
    """

    owns_session = False

    if db is None:
        db = SessionLocal()
        owns_session = True

    try:
        event = EventLog(
            event_type=event_type,
            event_detail=event_detail,
            event_timestamp=datetime.utcnow(),
        )
        db.add(event)
        db.commit()
    finally:
        if owns_session:
            db.close()
