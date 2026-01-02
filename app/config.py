"""
app/config.py
Application configuration
Environment-driven (Render compatible)
"""

import os

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")
