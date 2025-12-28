"""
KLResolute WhatsApp SaaS MVP
T-13 WebhookProcessor

Responsibilities:
- Accept a parsed inbound WhatsApp payload
- Execute the existing message pipeline
- Never deal with HTTP, FastAPI, or responses
"""

from __future__ import annotations

from app.services.message_service import MessageService


class WebhookProcessor:
    def __init__(self, message_service: MessageService) -> None:
        self._message_service = message_service

    def process_inbound_message(
        self,
        *,
        conversation,
        contact,
        inbound_text: str,
        from_number: str,
        to_number: str,
        client_id: str | None = None,
    ) -> None:
        """
        Execute the existing inbound → outbound pipeline.
        No return value. No HTTP concerns.
        """

        # This assumes your existing logic already:
        # - persists inbound message
        # - matches FAQ
        # - creates outbound message (dry-run)
        #
        # We are NOT changing that logic here.

        self._message_service.handle_inbound_message(
            conversation=conversation,
            contact=contact,
            inbound_text=inbound_text,
            from_number=from_number,
            to_number=to_number,
            client_id=client_id,
        )
