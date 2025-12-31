"""
File: app/messaging/admin_messenger.py
Path: app/messaging/admin_messenger.py

Project: KLResolute WhatsApp SaaS MVP

Purpose:
- Send admin-only confirmation and help messages
- Acts as the "UI" for admin commands
"""

from app.outbound.factory import get_meta_client


class AdminMessenger:
    def __init__(self):
        self._client = get_meta_client()

    def confirm(self, to_msisdn: str, text: str) -> None:
        """
        Send a confirmation message to an admin.
        Emoji + short text only.
        """
        self._client.send_session_message(
            to_msisdn=to_msisdn,
            text=text,
        )

    def help(self, to_msisdn: str) -> None:
        """
        Send admin help / command list.
        """
        help_text = (
            "🛠 Admin Commands:\n"
            "ADD CLIENT: <number>\n"
            "REMOVE CLIENT: <number>\n"
            "SEND: <number> <message>\n"
            "UPDATE: <message>\n"
            "HELP"
        )
        self.confirm(to_msisdn, help_text)
