"""
KLResolute WhatsApp SaaS MVP
T-09 Outbound delivery abstraction - Meta WhatsApp gateway (SKELETON)

IMPORTANT:
- This adapter is intentionally non-functional in MVP T-09.
- It is safe by default and will refuse to send unless explicitly enabled.
- Real Meta API sending is a later step (and still must never be called directly from the webhook).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .gateway import SendGateway, OutboundSendRequest, OutboundSendReceipt, SendStatus


@dataclass(frozen=True)
class MetaSendConfig:
    enabled: bool
    access_token: Optional[str] = None
    phone_number_id: Optional[str] = None
    api_base_url: str = "https://graph.facebook.com/v20.0"  # version can be updated later


class MetaSendGateway(SendGateway):
    def __init__(self, cfg: MetaSendConfig) -> None:
        self._cfg = cfg

    def send_text(self, req: OutboundSendRequest) -> OutboundSendReceipt:
        # Hard safety lock for T-09: even if instantiated, do not send unless enabled.
        if not self._cfg.enabled:
            return OutboundSendReceipt.now(
                status=SendStatus.DISABLED,
                detail="MetaSendGateway is disabled (T-09 safety lock). No message sent.",
                provider_message_id=None,
            )

        # If someone enables it prematurely without required config, fail safely.
        if not self._cfg.access_token or not self._cfg.phone_number_id:
            return OutboundSendReceipt.now(
                status=SendStatus.FAILED,
                detail="MetaSendGateway enabled but missing access_token and/or phone_number_id. No message sent.",
                provider_message_id=None,
            )

        # T-09 does not implement actual HTTP calls.
        # Later step: implement Graph API POST and map provider message id.
        return OutboundSendReceipt.now(
            status=SendStatus.FAILED,
            detail="MetaSendGateway is not implemented in T-09. No message sent.",
            provider_message_id=None,
        )
