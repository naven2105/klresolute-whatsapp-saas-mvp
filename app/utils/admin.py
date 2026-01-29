from __future__ import annotations

"""
File: app/utils/admin.py
Path: app/utils/admin.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Small shared helpers for admin checks.

Rules:
- Pure helpers only
- No DB access
- No outbound messaging
"""


def is_admin_message(sender: str, admin_allowlist: set[str]) -> bool:
    """
    True if sender is in the admin allowlist.
    """
    return bool(sender) and sender in admin_allowlist
