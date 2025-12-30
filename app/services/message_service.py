"""
File: app/services/message_service.py
Path: app/services/message_service.py

Project: KLResolute WhatsApp SaaS MVP

Purpose:
Authoritative service responsible for:
- Creating outbound Message drafts
- INLINE sending of session messages to Meta WhatsApp (MVP only)

Design rules:
- Webhook delegates outbound creation here
- This service MAY send session messages (INLINE MVP exception)
- Templates are NOT used here
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
import logging

from app.models import Message
from app.outbound.factory import get_meta_client

logger = logging.getLogger("message_service")

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
        to_number: str | None = None,
    ) -> None:
        if not selected_response or not to_number:
            return

        outbound = self._create_outbound_message(
            inbound_message_id=inbound_message_id,
            conversation_id=conversation_id,
            message_text=selected_response,
        )

        if not outbound:
            return

        # ---- INLINE SEND (MVP) ----
        try:
            client = get_meta_client()
            client.send_session_text(
                to_msisdn=to_number,
                text=selected_response,
            )
            logger.info("Sent session message to %s", to_number)
        except Exception:
            logger.exception("Failed to send session message")

    def _create_outbound_message(
        self,
        *,
        inbound_message_id,
        conversation_id,
        message_text: str,
    ) -> Message | None:

        idempotency_key = f"{_IDEMPOTENCY_PREFIX}{inbound_message_id}"

        existing = (
            self._db.query(Message)
            .filter(
                Message.conversation_id == conversation_id,
                Message.direction == "outbound",
                Message.provider_message_id == idempotency_key,
            )
            .first()
        )
        if existing:
            return None

        last_same_text = (
            self._db.query(Message)
            .filter(
                Message.conversation_id == conversation_id,
                Message.direction == "outbound",
                Message.message_text == message_text,
            )
            .order_by(Message.stored_at.desc())
            .first()
        )

        if last_same_text and last_same_text.stored_at:
            now = datetime.now(timezone.utc)
            last = last_same_text.stored_at.astimezone(timezone.utc)
            if (now - last) < timedelta(minutes=2):
                return None

        outbound = Message(
            conversation_id=conversation_id,
            direction="outbound",
            message_text=message_text,
            provider_message_id=idempotency_key,
        )

        self._db.add(outbound)
        self._db.commit()
        self._db.refresh(outbound)

        return outbound
