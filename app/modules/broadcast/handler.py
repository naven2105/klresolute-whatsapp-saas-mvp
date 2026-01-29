from __future__ import annotations

"""
File: app/modules/broadcast/handler.py
Path: app/modules/broadcast/handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Broadcast module entry point.
"""

from sqlalchemy.orm import Session

from app.messaging.client_messenger import send_message
from app.modules.broadcast.repo import get_active_staff_numbers
from app.modules.broadcast.service import validate_broadcast


def handle_broadcast(
    *,
    db: Session,
    client_code: str,
    template_name: str,
    text: str,
):
    """
    Admin-triggered broadcast.
    """

    validate_broadcast(
        template_name=template_name,
        text=text,
    )

    recipients = get_active_staff_numbers(
        db,
        client_code=client_code,
    )

    for msisdn in recipients:
        send_message(
            to_number=msisdn,
            template_name=template_name,
            language_code="en_US",
            body_params=[text],
        )
