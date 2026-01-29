from __future__ import annotations

"""
File: app/modules/broadcast/service.py
Path: app/modules/broadcast/service.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Broadcast business rules and validation.
"""

from app.modules.broadcast.templates import BROADCAST_TEMPLATES


def validate_broadcast(*, template_name: str, text: str | None):
    if template_name not in BROADCAST_TEMPLATES:
        raise ValueError(f"Template not allowed: {template_name}")

    if not text:
        raise ValueError("Broadcast text cannot be empty")
