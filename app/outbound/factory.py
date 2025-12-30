"""
File: app/outbound/factory.py
Path: app/outbound/factory.py

Project: KLResolute WhatsApp SaaS MVP

Purpose:
- Construct and reuse outbound Meta WhatsApp client
- NO web framework imports allowed
"""

from __future__ import annotations

from app.outbound.meta import MetaWhatsAppClient
from app.outbound.settings import load_meta_settings


_meta_client: MetaWhatsAppClient | None = None


def get_meta_client() -> MetaWhatsAppClient:
    global _meta_client
    if _meta_client is None:
        settings = load_meta_settings()
        _meta_client = MetaWhatsAppClient(settings=settings)
    return _meta_client
