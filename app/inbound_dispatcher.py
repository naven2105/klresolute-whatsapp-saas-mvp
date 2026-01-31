from __future__ import annotations

"""
File: app/inbound_dispatcher.py
Project: KLResolute WhatsApp SaaS MVP

LOCKED:
- No DB writes
- No behaviour changes
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

logger = logging.getLogger("inbound.dispatcher")


# -------------------------------------------------
# Helpers
# -------------------------------------------------

def _safe_execute(db: Session, stmt, params):
    """
    Guardrail:
    - If session is in failed state, rollback first
    """
    try:
        return db.execute(stmt, params)
    except Exception:
        logger.error("DISPATCH_DB_EXEC_FAILED | forcing rollback", exc_info=True)
        db.rollback()
        raise


def _send_unknown_sender(db: Session, sender: str, business_msisdn: str) -> None:
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

    if not row:
        logger.error(
            "UNKNOWN_SENDER_MESSAGE_MISSING | business=%s",
            business_msisdn,
        )

    send_message(
        to_number=sender,
        text=row["message_text"] if row else "Access restricted.",
    )


def _send_magen_staff_auto_response(db: Session, sender: str, business_msisdn: str) -> None:
    row = (
        _safe_execute(
            db,
            text(
                """
                SELECT cm.message_text
                FROM client_messages cm
                JOIN whatsapp_numbers w ON w.client_id = cm.client_id
                WHERE w.destination_number = :business
                  AND cm.message_key = 'staff_unknown'
                  AND cm.is_active = TRUE
                LIMIT 1
                """
            ),
            {"business": business_msisdn},
        )
        .mappings()
        .first()
    )

    if not row:
        logger.error(
            "MAGEN_STAFF_MESSAGE_MISSING | business=%s",
            business_msisdn,
        )

    send_message(
        to_number=sender,
        text=row["message_text"]
        if row
        else "Command not recognised. Use inspection commands only.",
    )


def _render_menu(menu: dict) -> str:
    lines = [menu.get("title", ""), ""]
    for section in menu.get("sections", []):
        lines.append(section.get("title", ""))
        for cmd in section.get("commands", []):
            lines.append(cmd)
        lines.append("")
    return "\n".join(lines).strip()


def _send_menu(*, db: Session, sender: str, business_msisdn: str, menu_key: str) -> None:
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

    if not row:
        logger.error(
            "MENU_MISSING | business=%s | menu_key=%s",
            business_msisdn,
            menu_key,
        )

    send_message(
        to_number=sender,
        text=_render_menu(row["menu_json"]) if row else "Menu unavailable.",
    )


# -------------------------------------------------
# Dispatcher
# -------------------------------------------------

def dispatch(*, db: Session, msg: dict, sender: str, business_msisdn: str) -> bool:
    # 🚨 CRITICAL GUARDRAIL
    try:
        db.rollback()
    except Exception:
        logger.warning("DISPATCH_ROLLBACK_FAILED", exc_info=True)

    profile = get_client_profile(business_msisdn)

    if not profile:
        logger.warning(
            "PROFILE_NOT_FOUND | sender=%s | business=%s",
            sender,
            business_msisdn,
        )
        _send_unknown_sender(db, sender, business_msisdn)
        return True

    # -------------------------------------------------
    # JOIN handling (early, single path)
    # -------------------------------------------------
    try:
        if join_handler.handle(
            db=db,
            msg=msg,
            sender=sender,
            business_msisdn=business_msisdn,
        ):
            logger.info(
                "JOIN_HANDLED_EARLY | sender=%s | business=%s",
                sender,
                business_msisdn,
            )
            return True
    except Exception:
        logger.error(
            "JOIN_HANDLER_FAILED | sender=%s | business=%s",
            sender,
            business_msisdn,
            exc_info=True,
        )

    # -------------------------------------------------
    # Workflow modules
    # -------------------------------------------------
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

    # -------------------------------------------------
    # Fallbacks
    # -------------------------------------------------
    if profile.client_code == "MAGEN":
        if is_admin_message(db=db, sender=sender, business_msisdn=business_msisdn):
            _send_menu(
                db=db,
                sender=sender,
                business_msisdn=business_msisdn,
                menu_key="admin_menu",
            )
            return True

        _send_magen_staff_auto_response(db, sender, business_msisdn)
        return True

    if is_admin_message(db=db, sender=sender, business_msisdn=business_msisdn):
        _send_menu(
            db=db,
            sender=sender,
            business_msisdn=business_msisdn,
            menu_key="admin_menu",
        )
        return True

    _send_menu(
        db=db,
        sender=sender,
        business_msisdn=business_msisdn,
        menu_key="customer_menu",
    )
    return True
