"""
KLResolute WhatsApp SaaS MVP
T-09 Outbound delivery abstraction - factory

One place to decide which gateway to use.
Default must remain DRY-RUN to preserve MVP guardrails.
"""

from __future__ import annotations

from dataclasses import dataclass

from .dry_run import DryRunSendGateway
from .gateway import SendGateway
from .meta import MetaSendGateway, MetaSendConfig


@dataclass(frozen=True)
class OutboundDeliverySettings:
    """
    Keep this separate from your app settings to avoid forcing a refactor.
    You can map your existing Settings -> this dataclass inside app startup.
    """
    mode: str = "dry_run"  # "dry_run" | "disabled" | "meta"
    meta_enabled: bool = False
    meta_access_token: str | None = None
    meta_phone_number_id: str | None = None
    meta_api_base_url: str = "https://graph.facebook.com/v20.0"


def build_send_gateway(s: OutboundDeliverySettings) -> SendGateway:
    mode = (s.mode or "dry_run").strip().lower()

    if mode == "disabled":
        # Disabled == still safe; behave like DRY_RUN but mark it as disabled if called.
        # We keep it simple: use Meta gateway in disabled mode to return DISABLED receipts.
        return MetaSendGateway(MetaSendConfig(enabled=False))

    if mode == "meta":
        return MetaSendGateway(
            MetaSendConfig(
                enabled=bool(s.meta_enabled),
                access_token=s.meta_access_token,
                phone_number_id=s.meta_phone_number_id,
                api_base_url=s.meta_api_base_url,
            )
        )

    # Default and recommended for now
    return DryRunSendGateway()
