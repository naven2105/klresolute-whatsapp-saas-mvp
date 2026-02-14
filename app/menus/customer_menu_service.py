from __future__ import annotations

"""
File: app/menus/customer_menu_service.py
Path: app/menus/customer_menu_service.py
Project: KLResolute WhatsApp SaaS MVP

Sprint: Full UUID Identity Migration

Purpose:
DB-backed customer menu sender.

RULE (UPDATED):
- Accept UUID client_id
- No integer resolution
- No klresolute_client_id usage
- Single identity model (UUID only)
"""

import logging

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.menus.menu_renderer import render_menu_text
from app.messaging.client_messenger import send_message

logger = logging.getLogger("menus.customer_menu_service")


def _resolve_business_number(
    db: Session,
    *,
    client_id: str,
) -> str | None:
    try:
        row = (
            db.execute(
                text(
                    """
                    SELECT destination_number
                    FROM whatsapp_numbers
                    WHERE client_id = :client_id
                      AND status = 'active'
                    LIMIT 1
                    """
                ),
                {"client_id": client_id},
            )
            .mappings()
            .first()
        )

        if not row:
            logger.error(
                "MENU_BUSINESS_NUMBER_NOT_FOUND | client_id=%s",
                client_id,
            )
            return None

        return row["destination_number"]

    except Exception as exc:
        logger.exception(
            "MENU_BUSINESS_RESOLUTION_FAIL | client_id=%s | err=%s",
            client_id,
            exc,
        )
        return None


def send_customer_menu_from_db(
    *,
    db: Session,
    client_id: str,
    sender: str,
    menu_key: str = "customer_menu",
) -> None:

    logger.info(
        "MENU_SERVICE_ENTER | client_id=%s | type=%s",
        client_id,
        type(client_id).__name__,
    )

    if not client_id:
        logger.error("MENU_CLIENT_ID_MISSING")
        return

    business_msisdn = _resolve_business_number(
        db,
        client_id=client_id,
    )

    if not business_msisdn:
        return

    row = (
        db.execute(
            text(
                """
                SELECT menu_json
                FROM client_menus
                WHERE client_id = :client_id
                  AND menu_key = :menu_key
                  AND is_active = TRUE
                LIMIT 1
                """
            ),
            {"client_id": client_id, "menu_key": menu_key},
        )
        .mappings()
        .first()
    )

    if not row:
        logger.error(
            "MENU_NOT_FOUND | client_id=%s | key=%s",
            client_id,
            menu_key,
        )
        return

    text_out = render_menu_text(row["menu_json"])

    send_message(
        db=db,
        business_msisdn=business_msisdn,
        to_number=sender,
        text=text_out,
    )

    logger.info(
        "MENU_SENT | client_id=%s | sender=%s",
        client_id,
        sender,
    )
