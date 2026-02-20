from __future__ import annotations

"""
File: tenant_resolver.py
Path: app/platform/tenant_resolver.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Resolve inbound WhatsApp phone_number_id → tenant.

Architecture Rules:
- Resolution strictly via whatsapp_phone_number_id
- Must be active tenant
- No fallback
- No default tenant
- Hard fail if not found
- Returns immutable routing context
"""

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger("platform.tenant_resolver")


@dataclass(frozen=True)
class TenantContext:
    restaurant_id: str
    name: str
    table_prefix: str
    whatsapp_display_number: str
    staff_notification_number: str | None


def resolve_tenant_by_phone_number_id(
    db: Session,
    phone_number_id: str,
) -> TenantContext:
    """
    Resolve tenant using whatsapp_phone_number_id.

    Raises:
        ValueError if tenant not found or inactive.
    """

    logger.info(
        "TENANT_RESOLVE_START | phone_number_id=%s",
        phone_number_id,
    )

    if not phone_number_id:
        logger.error("TENANT_RESOLVE_INVALID | reason=missing_phone_number_id")
        raise ValueError("phone_number_id required")

    result = db.execute(
        text(
            """
            SELECT
                id,
                name,
                table_prefix,
                whatsapp_display_number,
                staff_notification_number,
                is_active
            FROM restaurants
            WHERE whatsapp_phone_number_id = :pid
            LIMIT 1
            """
        ),
        {"pid": phone_number_id},
    ).mappings().first()

    if not result:
        logger.error(
            "TENANT_RESOLVE_FAILED | reason=not_found | phone_number_id=%s",
            phone_number_id,
        )
        raise ValueError("Tenant not found")

    if not result["is_active"]:
        logger.error(
            "TENANT_RESOLVE_FAILED | reason=inactive | phone_number_id=%s",
            phone_number_id,
        )
        raise ValueError("Tenant inactive")

    context = TenantContext(
        restaurant_id=str(result["id"]),
        name=result["name"],
        table_prefix=result["table_prefix"],
        whatsapp_display_number=result["whatsapp_display_number"],
        staff_notification_number=result["staff_notification_number"],
    )

    logger.info(
        "TENANT_RESOLVE_SUCCESS | restaurant_id=%s | prefix=%s",
        context.restaurant_id,
        context.table_prefix,
    )

    return context
