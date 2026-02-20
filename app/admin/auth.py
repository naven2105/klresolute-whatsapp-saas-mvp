from __future__ import annotations

"""
File: app/admin/auth.py
Path: app/admin/auth.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Minimal admin auth dependency for protecting admin-only endpoints.

Design:
- Does not alter existing admin routers (only used where imported)
- Uses env var ADMIN_TOKEN
- Accepts token via:
  - X-Admin-Token header, or
  - Authorization: Bearer <token>

If ADMIN_TOKEN is not set:
- Raise 500 for protected endpoints with a clear message
"""

import os
from typing import Optional

from fastapi import Header, HTTPException


def require_admin_user(
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> bool:
    expected = os.getenv("ADMIN_TOKEN")

    if not expected:
        raise HTTPException(
            status_code=500,
            detail="ADMIN_TOKEN is not set on the server. Set ADMIN_TOKEN to enable admin endpoints.",
        )

    token = (x_admin_token or "").strip()

    if not token and authorization:
        auth = authorization.strip()
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()

    if not token or token != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")

    return True