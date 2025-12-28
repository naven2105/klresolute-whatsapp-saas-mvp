"""
KLResolute WhatsApp SaaS MVP
T-09 Outbound delivery abstraction - DRY-RUN gateway

This gateway never sends anything.
It simply returns a receipt that indicates a simulated send.
"""

from __future__ import annotations

from .gateway import SendGateway, OutboundSendRequest, OutboundSendReceipt, SendStatus


class DryRunSendGateway(SendGateway):
    def send_text(self, req: OutboundSendRequest) -> OutboundSendReceipt:
        # No side effects. Never raises. Never calls external services.
        detail = (
            "DRY_RUN: outbound delivery simulated (not sent). "
            f"to={req.to_number} message_id={req.message_id}"
        )
        return OutboundSendReceipt.now(status=SendStatus.DRY_RUN, detail=detail, provider_message_id=None)
