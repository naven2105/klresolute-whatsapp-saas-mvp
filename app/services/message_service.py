"""
File: app/services/message_service.py

Project: KLResolute WhatsApp SaaS MVP

Purpose:
Authoritative service responsible for creating outbound Message drafts (dry-run).
Implements:
- Inbound-anchored idempotency: at most ONE outbound draft per inbound message_id
- H-01 time-window deduplication: suppress repeat outbound drafts within 2 minutes

Design rules:
- Outbound Message inserts MUST happen only here
- Webhook module delegates outbound creation to this service
- No external sending is performed here
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from app.models import Message


_IDEMPOTENCY_PREFIX = "parent_inbound:"


class MessageService:
    def __init__(self, db: Session):
        self._db = db

    def handle_inbound_message(
        self,
        *,
        inbound_message_id,
        conversation_id,
        inbound_text: str,
        selected_response: str | None,
    ) -> None:
        """
        Entry point for outbound creation for a given inbound message.

        inbound_message_id:
            The persisted inbound Message.message_id (UUID). Used as the idempotency anchor.
        """
        if not selected_response:
            return

        self._create_outbound_message(
            inbound_message_id=inbound_message_id,
            conversation_id=conversation_id,
            message_text=selected_response,
        )

    def _create_outbound_message(
        self,
        *,
        inbound_message_id,
        conversation_id,
        message_text: str,
    ) -> Message | None:
        """
        Create an outbound draft if allowed.

        Guarantees:
        1) Inbound-anchored idempotency:
           - If an outbound draft already exists for this inbound_message_id, do nothing.
        2) H-01 time-window deduplication (secondary):
           - If the same outbound text exists in this conversation within 2 minutes, suppress.
        """

        # --------------------------------------------------------------
        # Idempotency (authoritative): 1 outbound per inbound message_id
        # --------------------------------------------------------------
        idempotency_key = f"{_IDEMPOTENCY_PREFIX}{inbound_message_id}"

        existing_for_inbound = (
            self._db.query(Message)
            .filter(
                Message.conversation_id == conversation_id,
                Message.direction == "outbound",
                Message.provider_message_id == idempotency_key,
            )
            .first()
        )
        if existing_for_inbound:
            return None

        # --------------------------------------------------------------
        # H-01 (secondary): time-window suppression for repeat replies
        # --------------------------------------------------------------
        last_outbound_same_text = (
            self._db.query(Message)
            .filter(
                Message.conversation_id == conversation_id,
                Message.direction == "outbound",
                Message.message_text == message_text,
            )
            .order_by(Message.stored_at.desc())
            .first()
        )

        if last_outbound_same_text and last_outbound_same_text.stored_at:
            now_utc = datetime.now(timezone.utc)
            last_utc = last_outbound_same_text.stored_at.astimezone(timezone.utc)

            if (now_utc - last_utc) < timedelta(minutes=2):
                return None

        # --------------------------------------------------------------
        # Persist outbound draft (dry-run)
        # --------------------------------------------------------------
        outbound = Message(
            conversation_id=conversation_id,
            direction="outbound",
            message_text=message_text,
            # Internal marker used for idempotency (safe for dry-run)
            provider_message_id=idempotency_key,
        )

        self._db.add(outbound)
        self._db.commit()
        self._db.refresh(outbound)

        return outbound
