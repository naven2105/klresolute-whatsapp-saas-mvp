"""
File: app/admin/__init__.py

Project: KLResolute WhatsApp SaaS MVP

Purpose:
Admin package for read-only operational visibility (T-18).

Design rules:
- Read-only endpoints only (GET)
- No business logic here
- No writes, no side effects
"""

from .routes import router as admin_router
