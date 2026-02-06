"""
File: app/outbound/factory.py
Path: app/outbound/factory.py

Project: KLResolute WhatsApp SaaS MVP

Purpose:
- Construct and reuse outbound Meta WhatsApp clients
- One client per business (WABA), cached by business_msisdn
- Absolutely no imports from settings module
"""

from __future__ import annotations

import os
from typing import Dict

from app.outbound.meta import MetaWhatsAppClient


# Cache Meta clients per business_msisdn
_meta_clients: Dict[str, MetaWhatsAppClient] = {}


def get_meta_client(*, business_msisdn: str | None = None) -> MetaWhatsAppClient:
    """
    Return a MetaWhatsAppClient scoped to the given business_msisdn.

    If business_msisdn is None, falls back to default env-based client
    (backward compatible, but should be avoided for multi-client paths).
    """
    key = business_msisdn or "__default__"

    if key not in _meta_clients:
        access_token = os.getenv("META_WA_ACCESS_TOKEN")
        phone_number_id = os.getenv("META_WA_PHONE_NUMBER_ID")
        api_version = os.getenv("META_WA_API_VERSION", "v20.0")

        if not access_token or not phone_number_id:
            raise RuntimeError(
                "META_WA_ACCESS_TOKEN or META_WA_PHONE_NUMBER_ID not set"
            )

        settings = type(
            "MetaSettings",
            (),
            {
                "access_token": access_token,
                "messages_url": (
                    f"https://graph.facebook.com/"
                    f"{api_version}/"
                    f"{phone_number_id}/messages"
                ),
            },
        )()

        _meta_clients[key] = MetaWhatsAppClient(settings=settings)

    return _meta_clients[key]
