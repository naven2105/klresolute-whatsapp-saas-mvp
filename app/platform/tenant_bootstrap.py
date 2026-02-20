from __future__ import annotations

"""
File: tenant_bootstrap.py
Path: app/platform/tenant_bootstrap.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Create dedicated per-tenant tables.

Architecture Rules:
- One tenant = isolated tables
- Naming: <table_prefix>__<entity>
- No shared operational tables
- Idempotent creation
- Transactional execution
- Hard fail on any error
"""

import logging
from typing import List

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.platform.tenant_validator import validate_table_prefix

logger = logging.getLogger("platform.tenant_bootstrap")


TENANT_ENTITIES: List[str] = [
    "customers",
    "menu_items",
    "specials",
    "beverages",
    "booking_requests",
    "events",
    "announcements",
    "campaigns",
    "broadcast_logs",
]


def bootstrap_tenant_tables(db: Session, table_prefix: str) -> None:
    """
    Creates all required tenant tables.

    Raises:
        Exception on failure (transaction will rollback)
    """

    logger.info("TENANT_BOOTSTRAP_START | prefix=%s", table_prefix)

    validate_table_prefix(table_prefix)

    try:
        with db.begin():  # transactional guard rail

            for entity in TENANT_ENTITIES:
                table_name = f"{table_prefix}__{entity}"

                logger.info(
                    "TENANT_BOOTSTRAP_CREATE_TABLE | table=%s",
                    table_name,
                )

                create_sql = f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                """

                db.execute(text(create_sql))

        logger.info("TENANT_BOOTSTRAP_SUCCESS | prefix=%s", table_prefix)

    except Exception as e:
        logger.exception(
            "TENANT_BOOTSTRAP_FAILED | prefix=%s | error=%s",
            table_prefix,
            str(e),
        )
        raise
