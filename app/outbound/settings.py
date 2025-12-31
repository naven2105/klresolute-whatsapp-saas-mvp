"""
app/outbound/settings.py
KLResolute WhatsApp SaaS MVP
Outbound Settings

Purpose:
- Centralised outbound (Meta WhatsApp Cloud API) configuration.
- Keep secrets out of code via environment variables.

Notes:
- These are required for sending template messages:
  - META_WA_ACCESS_TOKEN
  - META_WA_PHONE_NUMBER_ID
- Optional:
  - META_WA_API_VERSION (defaults to v20.0 if not provided)
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            f"Set it in your .env / Render / shell before running."
        )
    return value


@dataclass(frozen=True)
class MetaWhatsAppSettings:
    api_version: str
    access_token: str
    phone_number_id: str

    @property
    def base_url(self) -> str:
        return f"https://graph.facebook.com/{self.api_version}"

    @property
    def messages_url(self) -> str:
        return f"{self.base_url}/{self.phone_number_id}/messages"


def load_meta_settings() -> MetaWhatsAppSettings:
    return MetaWhatsAppSettings(
        api_version=os.getenv("META_WA_API_VERSION", "v20.0").strip(),
        access_token=_require_env("META_WA_ACCESS_TOKEN"),
        phone_number_id=_require_env("META_WA_PHONE_NUMBER_ID"),
    )
