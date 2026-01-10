from __future__ import annotations
import uuid
from datetime import datetime
from app.db import get_db_session  # use YOUR existing session helper
from app.models import EventLog   # mapped to event_logs table

def log_event(
    *,
    client_id: uuid.UUID,
    event_type: str,
    event_detail: str,
    conversation_id: uuid.UUID | None = None,
    message_id: uuid.UUID | None = None,
) -> None:
    with get_db_session() as db:
        db.add(EventLog(
            event_id=uuid.uuid4(),
            client_id=client_id,
            conversation_id=conversation_id,
            message_id=message_id,
            event_type=event_type,
            event_detail=event_detail,
            event_timestamp=datetime.utcnow(),
        ))
        db.commit()
