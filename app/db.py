"""
KLResolute WhatsApp SaaS MVP
Database module (single-file)

Provides:
- SQLAlchemy engine + SessionLocal
- get_db() generator for FastAPI dependency injection
"""

from __future__ import annotations

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ---- Config ----
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

# ---- Engine + Session ----
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

def get_db():
    """
    FastAPI dependency:
    - opens a DB session
    - yields it to the request handler
    - always closes it afterwards
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
    