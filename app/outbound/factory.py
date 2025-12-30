"""
File: app/outbound/factory.py

Project: KLResolute WhatsApp SaaS MVP

Purpose:
T-09/T-24 Outbound delivery abstraction - factory

One place to decide which gateway to use.
Default must remain DRY-RUN to preserve MVP guardrails.

Modes:
- "dry_run" (default)
- "disabled"
- "meta" (real sending, still guarded by allowlist)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .dry_run import DryRunSendGateway
from .gateway import SendGateway
from .meta import MetaSendGateway, MetaSendConfig


@dataclass(frozen=True)
class OutboundDeliverySettings:
    """
    Keep this separate from your app settings to avoid forcing a refactor.
    You can map environment -> this dataclass inside app startup or in jobs.
    """
    mode: str = "dry_run"  # "dry_run" | "disabled" | "meta"
    meta_enabled: bool = False
    meta_access_token: str | None = None
    meta_phone_number_id: str | None = None
    meta_api_base_url: str = "https://graph.facebook.com/v20.0"
    test_allowlist: Sequence[str] = ()  # numbers allowed to receive real sends


def build_send_gateway(s: OutboundDeliverySettings) -> SendGateway:
    mode = (s.mode or "dry_run").strip().lower()

    if mode == "disabled":
        return MetaSendGateway(MetaSendConfig(enabled=False))

    if mode == "meta":
        return MetaSendGateway(
            MetaSendConfig(
                enabled=bool(s.meta_enabled),
                access_token=s.meta_access_token,
                phone_number_id=s.meta_phone_number_id,
                api_base_url=s.meta_api_base_url,
                test_allowlist=tuple(s.test_allowlist or ()),
            )
        )

    # Default and recommended for now
    return DryRunSendGateway()
