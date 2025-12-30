"""
File: app/outbound/factory.py
Path: app/outbound/factory.py

Project: KLResolute WhatsApp SaaS MVP

Purpose:
- Construct and reuse outbound Meta WhatsApp client
- Avoid import-time and attribute resolution issues
"""

from __future__ import annotations

from app.outbound.meta import MetaWhatsAppClient
from app.outbound.settings import MetaWhatsAppSettings
import os


_meta_client: MetaWhatsAppClient | None = None


def get_meta_client() -> MetaWhatsAppClient:
    global _meta_client

    if _meta_client is None:
        settings = MetaWhatsAppSettings(
            api_version=os.getenv("META_WA_API_VERSION", "v20.0"),
            access_token=os.getenv("META_WA_ACCESS_TOKEN"),
            phone_number_id=os.getenv("META_WA_PHONE_NUMBER_ID"),
        )

        _meta_client = MetaWhatsAppClient(settings=settings)

    return _meta_client
