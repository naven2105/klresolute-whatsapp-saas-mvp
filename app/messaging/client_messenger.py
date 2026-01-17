"""
File: app/messaging/client_messenger.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Thin messaging helpers for client-facing messages.
"""

from app.outbound.meta import MetaWhatsAppClient
from app.outbound.settings import load_meta_settings

_meta_client = MetaWhatsAppClient(settings=load_meta_settings())


def send_message(to_number: str, text: str) -> None:
    """
    Send a simple WhatsApp session message to a client.

    This is a thin wrapper used by handlers to avoid
    duplicating MetaWhatsAppClient setup logic.
    """
    _meta_client.send_session_message(
        to_msisdn=to_number,
        text=text,
    )
