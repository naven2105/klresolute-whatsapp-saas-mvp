"""
File: app/outbound/settings.py

Project: KLResolute WhatsApp SaaS MVP

Purpose:
Centralised outbound delivery settings.
Reads environment variables and exposes a typed config
used by the outbound delivery factory.

Design rules:
- No logic
- No DB access
- No sending
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class OutboundDeliverySettings:
    mode: str = "dry_run"  # dry_run | disabled | meta

    meta_enabled: bool = False
    meta_access_token: str | None = None
    meta_phone_number_id: str | None = None
    meta_api_base_url: str = "https://graph.facebook.com/v23.0"

    outbound_test_allowlist: tuple[str, ...] = ()


def load_outbound_settings() -> OutboundDeliverySettings:
    allowlist_raw = os.getenv("OUTBOUND_TEST_ALLOWLIST", "")
    allowlist = tuple(
        n.strip() for n in allowlist_raw.split(",") if n.strip()
    )

    return OutboundDeliverySettings(
        mode=os.getenv("OUTBOUND_MODE", "dry_run"),
        meta_enabled=os.getenv("META_ENABLED", "false").lower() == "true",
        meta_access_token=os.getenv("META_ACCESS_TOKEN"),
        meta_phone_number_id=os.getenv("META_PHONE_NUMBER_ID"),
        meta_api_base_url=os.getenv(
            "META_API_BASE_URL", "https://graph.facebook.com/v23.0"
        ),
        outbound_test_allowlist=allowlist,
    )
