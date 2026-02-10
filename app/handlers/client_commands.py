from __future__ import annotations

"""
File: app/handlers/client_commands.py
Project: KLResolute WhatsApp SaaS MVP

ROLE (EXPLICIT & TEMPORARY):
Backward-compatible re-export wrapper.

This module exists ONLY to preserve legacy imports while the
dispatcher and downstream modules are progressively migrated.

CANONICAL ENTRY POINT:
- app/handlers/tier1_router.py::handle_client_command

HARD RULES:
- MUST NOT add logic here
- MUST NOT intercept, modify, or wrap calls
- MUST NOT raise exceptions
- MUST remain a direct pass-through

GUARD RAIL:
Any behavioural change here is considered a breaking change.

REMOVAL CONDITION:
This file may ONLY be removed once all imports across the codebase
have been migrated to tier1_router.py.
"""

from app.handlers.tier1_router import handle_client_command  # re-export (LOCKED)
