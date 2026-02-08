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
"""

import logging

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.outbound.factory import get_meta_client
from app.menus.menu_renderer import render_menu_text  # ✅ unified renderer

logger = logging.getLogger("menus.customer_menu_service")


def _resolve_client_uuid(
    db: Session,
    *,
    client_id_int: int,
) -> str | None:
    """
    Resolve UUID client_id from integer klresolute_client_id.
    """
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


def send_customer_menu_from_db(
    *,
    db: Session,
    client_id: str,
    sender: str,
    menu_key: str = "customer_menu",
) -> None:
    """
    Send customer menu using DB-backed menu.
    client_id is INTEGER (stringified) from Tier-1.
    """
    logger.info(
        "MENU_SERVICE_ENTER | client_id=%r | type=%s",
        client_id,
        type(client_id).__name__,
    )

    # ----------------------------------
    # Guard + parse integer client_id
    # ----------------------------------
    try:
        client_id_int = int(str(client_id))
    except Exception:
        logger.error(
            "MENU_CLIENT_ID_INVALID | client_id=%r",
            client_id,
        )
        return

    # ----------------------------------
    # Resolve UUID for menu lookup
    # ----------------------------------
    client_uuid = _resolve_client_uuid(
        db,
        client_id_int=client_id_int,
    )

    if not client_uuid:
        return

    # ----------------------------------
    # Fetch menu JSON
    # ----------------------------------
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

    # ----------------------------------
    # Render + send
    # ----------------------------------
    text_out = render_menu_text(row["menu_json"])
    meta = get_meta_client()

    meta.send_session_message(
        to_msisdn=sender,
        text=text_out,
    )

    logger.info(
        "MENU_SENT | client_uuid=%s | sender=%s",
        client_uuid,
        sender,
    )
