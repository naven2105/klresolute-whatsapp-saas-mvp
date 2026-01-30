from __future__ import annotations

"""
File: app/repos/client_messages_repo.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
DB access for client-specific message content.

Rules (LOCKED):
- DB reads only
- No Meta calls
- No business logic
- No fallbacks beyond safe defaults
"""

from sqlalchemy.orm import Session
from sqlalchemy import text


def get_client_message(
    *,
    db: Session,
    client_id: str,
    message_key: str,
) -> str | None:
    """
    Fetch active client message by key.

    Examples of message_key:
    - unknown_sender
    - unknown_command
    - join_prompt
    - staff_unknown
    """

    row = (
        db.execute(
            text(
                """
                SELECT message_text
                FROM client_messages
                WHERE client_id = :client_id
                  AND message_key = :message_key
                  AND is_active = TRUE
                LIMIT 1
                """
            ),
            {
                "client_id": client_id,
                "message_key": message_key,
            },
        )
        .mappings()
        .first()
    )

    if not row:
        return None

    return row["message_text"]
