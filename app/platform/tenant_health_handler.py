from __future__ import annotations

"""
File: tenant_health_handler.py
Path: app/platform/tenant_health_handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Sprint 1 health test.

Flow:
Inbound message →
Resolve tenant →
Insert row into <prefix>__events →
Send dummy response.

No business logic.
No routing beyond tenant resolution.
"""

import logging

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.platform.tenant_resolver import resolve_tenant_by_phone_number_id
from app.messaging.client_messenger import send_message

logger = logging.getLogger("platform.tenant_health")


def handle_health_test(
    db: Session,
    phone_number_id: str,
    sender_msisdn: str,
    message_text: str | None,
) -> None:
    """
    Sprint 1 health test handler.
    """

    logger.info(
        "TENANT_HEALTH_START | phone_number_id=%s | sender=%s",
        phone_number_id,
        sender_msisdn,
    )

    # 1️⃣ Resolve tenant (hard fail if not valid)
    tenant = resolve_tenant_by_phone_number_id(
        db=db,
        phone_number_id=phone_number_id,
    )

    events_table = f"{tenant.table_prefix}__events"

    try:
        with db.begin():

            logger.info(
                "TENANT_HEALTH_INSERT_EVENT | table=%s | sender=%s",
                events_table,
                sender_msisdn,
            )

            insert_sql = f"""
            INSERT INTO {events_table} (id, created_at)
            VALUES (gen_random_uuid(), NOW())
            """

            db.execute(text(insert_sql))

        logger.info(
            "TENANT_HEALTH_INSERT_SUCCESS | table=%s",
            events_table,
        )

    except Exception as e:
        logger.exception(
            "TENANT_HEALTH_FAILED | table=%s | error=%s",
            events_table,
            str(e),
        )
        raise

    # 2️⃣ Send dummy response
    send_message(
        phone_number_id=phone_number_id,
        to=sender_msisdn,
        text="Tenant resolved.",
    )

    logger.info(
        "TENANT_HEALTH_COMPLETE | prefix=%s",
        tenant.table_prefix,
    )
