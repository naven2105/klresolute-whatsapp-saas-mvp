"""
File: app/messaging/admin_messenger.py
Path: app/messaging/admin_messenger.py

Project: KLResolute WhatsApp SaaS MVP

Purpose:
- Send admin-only confirmation and help messages
- Acts as the "UI" for admin commands
"""

from sqlalchemy.orm import Session
from app.messaging.client_messenger import send_message


class AdminMessenger:
    def __init__(self, *, db: Session, business_msisdn: str):
        self._db = db
        self._business_msisdn = business_msisdn

    def confirm(self, to_msisdn: str, text: str) -> None:
        """
        Send a confirmation message to an admin.
        Emoji + short text only.
        """
        send_message(
            db=self._db,
            business_msisdn=self._business_msisdn,
            to_number=to_msisdn,
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
