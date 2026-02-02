from __future__ import annotations

"""
File: app/handlers/client_commands.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Backward-compatible wrapper.

NOTE:
The canonical Tier 1 entry point has moved to:
- app/handlers/tier1_router.py

Keep this file to avoid breaking existing imports until the dispatcher and
downstream modules are updated everywhere.
"""

from app.handlers.tier1_router import handle_client_command  # re-export
