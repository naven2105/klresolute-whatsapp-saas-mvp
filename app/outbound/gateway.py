"""
KLResolute WhatsApp SaaS MVP
T-09 Outbound delivery abstraction (still DRY-RUN)

This module defines a stable SendGateway interface and strongly-typed
request/receipt objects for outbound delivery.

Guardrails:
- This layer must be callable from services, but the webhook must still never send directly.
- Default behaviour remains DRY-RUN (store-only / simulate).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Protocol, Optional


class SendStatus(str, Enum):
    DRY_RUN = "dry_run"
    SENT = "sent"
    FAILED = "failed"
    DISABLED = "disabled"


@dataclass(frozen=True)
class OutboundSendRequest:
    """
    Represents an attempt to deliver a specific outbound message.

    Keep it minimal for MVP:
    - conversation_id / contact_id helps traceability
    - to_number is E.164 (e.g. 2783xxxxxxx)
    - body_text is the message text that *would* be delivered
    - message_id is your DB Message UUID (or equivalent) for idempotency tracing
    """
    message_id: str
    conversation_id: str
    contact_id: str
    to_number: str
    body_text: str

    # Optional metadata for later:
    from_number: Optional[str] = None  # business WA number (E.164)
    client_id: Optional[str] = None


@dataclass(frozen=True)
class OutboundSendReceipt:
    """
    Result of a delivery attempt (or simulated attempt).
    """
    status: SendStatus
    provider_message_id: Optional[str]
    detail: str
    created_at_utc: datetime

    @staticmethod
    def now(status: SendStatus, detail: str, provider_message_id: Optional[str] = None) -> "OutboundSendReceipt":
        return OutboundSendReceipt(
            status=status,
            provider_message_id=provider_message_id,
            detail=detail,
            created_at_utc=datetime.now(timezone.utc),
        )


class SendGateway(Protocol):
    """
    Abstract gateway for outbound delivery.
    """
    def send_text(self, req: OutboundSendRequest) -> OutboundSendReceipt:
        """
        Deliver a WhatsApp text message (or simulate it, depending on gateway).
        Must be fast and must not throw in normal cases.
        """
        ...
