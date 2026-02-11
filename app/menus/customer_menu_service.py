from __future__ import annotations

"""
File: app/menus/customer_menu_service.py
Path: app/menus/customer_menu_service.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
DB-backed customer menu sender.

RULE (MVP):
- Accept INTEGER client_id from Tier-1
- Resolve UUID client_id internally for client_menus
- Use single transport gateway
"""

import logging

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.menus.menu_renderer import render_menu_text
from app.messaging.client_messenger import send_message

logger = logging.getLogger("menus.customer_menu_service")


def _resolve_client_uuid(
    db: Session,
    *,
    client_id_int: int,
) -> str | None:
    try:
        row = (
            db.execute(
                text(
                    """
                    SELECT client_id
                    FROM whatsapp_numbers
                    WHERE klresolute_client_id = :cid
                      AND status = 'active'
                    LIMIT 1
                    """
                ),
                {"cid": client_id_int},
            )
            .mappings()
            .first()
        )

        if not row:
            logger.error(
                "MENU_CLIENT_UUID_NOT_FOUND | client_id_int=%s",
                client_id_int,
            )
            return None

        return str(row["client_id"])

    except Exception as exc:
        logger.exception(
            "MENU_CLIENT_UUID_RESOLUTION_FAIL | client_id_int=%s | err=%s",
            client_id_int,
            exc,
        )
        return None


def _resolve_business_number(
    db: Session,
    *,
    client_id_int: int,
) -> str | None:
    try:
        row = (
            db.execute(
                text(
                    """
                    SELECT destination_number
                    FROM whatsapp_numbers
                    WHERE klresolute_client_id = :cid
                      AND status = 'active'
                    LIMIT 1
                    """
                ),
                {"cid": client_id_int},
            )
            .mappings()
            .first()
        )

        if not row:
            logger.error(
                "MENU_BUSINESS_NUMBER_NOT_FOUND | client_id_int=%s",
                client_id_int,
            )
            return None

        return row["destination_number"]

    except Exception as exc:
        logger.exception(
            "MENU_BUSINESS_RESOLUTION_FAIL | client_id_int=%s | err=%s",
            client_id_int,
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
        "MENU_SERVICE_ENTER | client_id=%r | type=%s",
        client_id,
        type(client_id).__name__,
    )

    try:
        client_id_int = int(str(client_id))
    except Exception:
        logger.error(
            "MENU_CLIENT_ID_INVALID | client_id=%r",
            client_id,
        )
        return

    client_uuid = _resolve_client_uuid(
        db,
        client_id_int=client_id_int,
    )

    if not client_uuid:
        return

    business_msisdn = _resolve_business_number(
        db,
        client_id_int=client_id_int,
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
            {"client_id": client_uuid, "menu_key": menu_key},
        )
        .mappings()
        .first()
    )

    if not row:
        logger.error(
            "MENU_NOT_FOUND | client_uuid=%s | key=%s",
            client_uuid,
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
        "MENU_SENT | client_uuid=%s | sender=%s",
        client_uuid,
        sender,
    )
