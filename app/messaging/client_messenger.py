"""
File: app/messaging/client_messenger.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Thin messaging helpers for client-facing messages.
Supports both session messages and approved templates.
"""

from app.outbound.meta import MetaWhatsAppClient
from app.outbound.settings import load_meta_settings

_meta_client = MetaWhatsAppClient(settings=load_meta_settings())


def send_message(
    *,
    to_number: str,
    text: str | None = None,
    template_name: str | None = None,
    language_code: str = "en_US",
) -> None:
    """
    Send a WhatsApp message to a client.

    Supports:
    - Session text messages (inside 24h window)
    - Approved WhatsApp templates (guaranteed delivery)

    Exactly one of `text` or `template_name` must be provided.
    """

    if text and template_name:
        raise ValueError("Provide either text or template_name, not both")

    if text:
        _meta_client.send_session_message(
            to_msisdn=to_number,
            text=text,
        )
        return

    if template_name:
        _meta_client.send_template(
            to_msisdn=to_number,
            template_name=template_name,
            language_code=language_code,
        )
        return

    raise ValueError("Either text or template_name must be provided")
