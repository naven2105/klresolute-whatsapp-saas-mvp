from __future__ import annotations

"""
File: app/inbound_dispatcher.py
Project: KLResolute WhatsApp SaaS MVP

LOCKED:
- No DB writes
- Behaviour defined by DB + handlers
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.messaging.client_messenger import send_message
from app.profiles.client_profile import get_client_profile
from app.utils.admin import is_admin_message

from app.modules.join import handler as join_handler
from app.modules.inspection import handler as inspection_handler
from app.modules.survey import handler as survey_handler
from app.modules.broadcast import handler as broadcast_handler
from app.modules.orders import handler as orders_handler

from app.ui import emoji

logger = logging.getLogger("inbound.dispatcher")


# -------------------------------------------------
# Helpers
# -------------------------------------------------

def _safe_execute(db: Session, stmt, params):
    try:
        return db.execute(stmt, params)
    except Exception:
        logger.error("DISPATCH_DB_EXEC_FAILED | forcing rollback", exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass
        raise


def _reset_session(db: Session) -> None:
    try:
        db.rollback()
    except Exception:
        pass


def _send_unknown_sender(db: Session, sender: str, business_msisdn: str) -> None:
    _reset_session(db)

    row = (
        _safe_execute(
            db,
            text(
                """
                SELECT cm.message_text
                FROM client_messages cm
                JOIN whatsapp_numbers w ON w.client_id = cm.client_id
                WHERE w.destination_number = :business
                  AND cm.message_key = 'unknown_sender'
                  AND cm.is_active = TRUE
                LIMIT 1
                """
            ),
            {"business": business_msisdn},
        )
        .mappings()
        .first()
    )

    send_message(
        to_number=sender,
        text=row["message_text"] if row else "Access restricted.",
    )


def _render_menu(menu: dict) -> str:
    title = f"{emoji.MENU_TITLE} {menu.get('title', '')} {emoji.MENU_TITLE}".strip()
    lines = [title, ""]

    emoji_map = {
        "ORDER": emoji.ORDER,
        "SPECIALS": emoji.SPECIALS,
        "ABOUT": emoji.ABOUT,
        "FEEDBACK": emoji.FEEDBACK,
    }

    for section in menu.get("sections", []):
        lines.append(section.get("title", ""))
        for cmd in section.get("commands", []):
            key = cmd.upper()
            prefix = emoji_map.get(key, "")
            lines.append(f"{prefix} {cmd}".strip())
        lines.append("")

    return "\n".join(lines).strip()


def _send_menu(*, db: Session, sender: str, business_msisdn: str, menu_key: str) -> None:
    _reset_session(db)

    row = (
        _safe_execute(
            db,
            text(
                """
                SELECT m.menu_json
                FROM client_menus m
                JOIN whatsapp_numbers w ON w.client_id = m.client_id
                WHERE w.destination_number = :business
                  AND m.menu_key = :menu_key
                  AND m.is_active = TRUE
                LIMIT 1
                """
            ),
            {"business": business_msisdn, "menu_key": menu_key},
        )
        .mappings()
        .first()
    )

    send_message(
        to_number=sender,
        text=_render_menu(row["menu_json"]) if row else "Menu unavailable.",
    )


# -------------------------------------------------
# Dispatcher
# -------------------------------------------------

def dispatch(*, db: Session, msg: dict, sender: str, business_msisdn: str) -> bool:
    try:
        db.rollback()
    except Exception:
        pass

    profile = get_client_profile(business_msisdn, db=db)

    if not profile:
        _send_unknown_sender(db, sender, business_msisdn)
        return True

    if join_handler.handle(
        db=db,
        msg=msg,
        sender=sender,
        business_msisdn=business_msisdn,
    ):
        _send_menu(
            db=db,
            sender=sender,
            business_msisdn=business_msisdn,
            menu_key="customer_menu",
        )
        return True

    for module in profile.enabled_modules:

        if module == "orders" and orders_handler.handle(
            db=db, msg=msg, sender=sender, business_msisdn=business_msisdn
        ):
            return True

        if module == "inspection" and inspection_handler.handle(
            db=db, msg=msg, sender=sender, business_msisdn=business_msisdn
        ):
            return True

        if module == "survey" and survey_handler.handle(
            db=db, msg=msg, sender=sender, business_msisdn=business_msisdn
        ):
            return True

        if module == "broadcast" and broadcast_handler.handle(
            db=db, msg=msg, sender=sender, business_msisdn=business_msisdn
        ):
            return True

    _send_menu(
        db=db,
        sender=sender,
        business_msisdn=business_msisdn,
        menu_key="customer_menu",
    )
    return True
