"""
File: app/outbound/factory.py
Path: app/outbound/factory.py

Project: KLResolute WhatsApp SaaS MVP

Purpose:
- Construct and reuse outbound Meta WhatsApp client
- Absolutely no imports from settings module
"""

from __future__ import annotations

import os
from app.outbound.meta import MetaWhatsAppClient


_meta_client: MetaWhatsAppClient | None = None


def get_meta_client() -> MetaWhatsAppClient:
    global _meta_client

    if _meta_client is None:
        settings = type(
            "MetaSettings",
            (),
            {
                "access_token": os.getenv("META_WA_ACCESS_TOKEN"),
                "messages_url": (
                    f"https://graph.facebook.com/"
                    f"{os.getenv('META_WA_API_VERSION', 'v20.0')}/"
                    f"{os.getenv('META_WA_PHONE_NUMBER_ID')}/messages"
                ),
            },
        )()

        _meta_client = MetaWhatsAppClient(settings=settings)

    return _meta_client
