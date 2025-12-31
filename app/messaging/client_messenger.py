"""
File: app/messaging/client_messenger.py
Path: app/messaging/client_messenger.py

Project: KLResolute WhatsApp SaaS MVP

Purpose:
- Send messages to clients
- Handles operational (SEND) and broadcast (UPDATE) messages
"""

from app.outbound.factory import get_meta_client


class ClientMessenger:
    def __init__(self):
        self._client = get_meta_client()

    def send_session(self, to_msisdn: str, text: str) -> None:
        """
        One-to-one operational message.
        """
        self._client.send_session_message(
            to_msisdn=to_msisdn,
            text=text,
        )

    def send_update(self, to_msisdn: str, message: str) -> None:
        """
        One-to-many business update using approved template.
        """
        self._client.send_generic_business_update_template(
            to_msisdn=to_msisdn,
            blob_text=message,
        )
