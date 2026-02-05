from __future__ import annotations

"""
File: app/menus/customer_menu_service.py
Path: app/menus/customer_menu_service.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
DB-only customer menu loader + sender.

Rules (LOCKED):
- Menus are loaded from public.client_menus (menu_json JSONB).
- No code-based per-client menus. No fallback menus.
- Must log loudly and fail if menu is missing/inactive/malformed.
"""

import logging
from typing import Any, Dict

from sqlalchemy.orm import Session
from sqlalchemy import text as sql_text

from app.outbound.factory import get_meta_client
from app.menus.menu_renderer import render_menu_text

logger = logging.getLogger("menus.customer_menu_service")


def _load_menu_json_from_db(
    *,
    db: Session,
    client_id: str,
    menu_key: str,
) -> Dict[str, Any]:
    row = (
        db.execute(
            sql_text(
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
            "MENU_MISSING | client_id=%s | menu_key=%s | source=client_menus",
            client_id,
            menu_key,
        )
        raise ValueError(f"Menu not found or inactive for client_id={client_id}, menu_key={menu_key}")

    menu_json = row.get("menu_json")
    if not isinstance(menu_json, dict):
        logger.error(
            "MENU_INVALID_TYPE | client_id=%s | menu_key=%s | type=%s",
            client_id,
            menu_key,
            type(menu_json).__name__,
        )
        raise ValueError(f"Menu JSON is not an object for client_id={client_id}, menu_key={menu_key}")

    return menu_json


def send_customer_menu_from_db(
    *,
    db: Session,
    client_id: str,
    sender_msisdn: str,
    menu_key: str = "customer_menu",
) -> None:
    """
    Loads a menu from DB and sends it to the user.
    Hard-fails on missing/inactive/malformed menu (no fallback).
    """
    if not client_id:
        logger.error("MENU_GUARD_FAIL | reason=missing_client_id | sender=%s", sender_msisdn)
        raise ValueError("client_id is required")

    if not sender_msisdn:
        logger.error("MENU_GUARD_FAIL | reason=missing_sender_msisdn | client_id=%s", client_id)
        raise ValueError("sender_msisdn is required")

    logger.info(
        "MENU_SEND_ATTEMPT | client_id=%s | sender=%s | menu_key=%s",
        client_id,
        sender_msisdn,
        menu_key,
    )

    menu_json = _load_menu_json_from_db(db=db, client_id=client_id, menu_key=menu_key)
    text = render_menu_text(menu_json)

    meta = get_meta_client()
    meta.send_session_message(to_msisdn=sender_msisdn, text=text)

    logger.info(
        "MENU_SEND_OK | client_id=%s | sender=%s | menu_key=%s",
        client_id,
        sender_msisdn,
        menu_key,
    )
