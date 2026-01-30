from __future__ import annotations

"""
File: app/inbound_dispatcher.py
Project: KLResolute WhatsApp SaaS MVP

Step 4:
- MAGEN staff:
    - Unknown command → strict auto-response
    - NO menus
- MAGEN admin:
    - Unknown command → admin menu

LOCKED:
- No DB writes
- No behaviour changes for other clients
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.messaging.client_messenger import send_message
from app.profiles.client_profile import get_client_profile
from app.utils.admin import is_admin_message

# ---- Modules ----
from app.modules.inspection import handler as inspection_handler
from app.modules.survey import handler as survey_handler
from app.modules.broadcast import handler as broadcast_handler
from app.modules.orders import handler as orders_handler

logger = logging.getLogger("inbound.dispatcher")


# -------------------------------------------------
# Client resolution (FIX)
# -------------------------------------------------

def _resolve_client_profile(db: Session, business_msisdn: str):
    """
    Resolve client profile via whatsapp_numbers → clients.
    """
    try:
        row = (
            db.execute(
                text(
                    """
                    SELECT c.client_code
                    FROM whatsapp_numbers w
                    JOIN clients c ON c.client_id = w.client_id
                    WHERE w.destination_number = :business
                      AND w.status = 'active'
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
                "DISPATCH_NO_CLIENT | business=%s",
                business_msisdn,
            )
            return None

        return get_client_profile(row["client_code"])

    except Exception as exc:
        logger.error(
            "DISPATCH_CLIENT_LOOKUP_FAIL | business=%s | error=%s",
            business_msisdn,
            exc,
            exc_info=True,
        )
        return None


# -------------------------------------------------
# Message helpers
# -------------------------------------------------

def _send_unknown_sender(db: Session, sender: str, business_msisdn: str) -> None:
    row = (
        db.execute(
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


def _send_magen_staff_auto_response(
    db: Session, sender: str, business_msisdn: str
) -> None:
    row = (
        db.execute(
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


def _send_menu(
    *, db: Session, sender: str, business_msisdn: str, menu_key: str
) -> None:
    row = (
        db.execute(
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
        text=_render_menu(row["menu_json"])
        if row
        else "Menu unavailable.",
    )


# -------------------------------------------------
# Dispatcher
# -------------------------------------------------

def dispatch(
    *,
    db: Session,
    msg: dict,
    sender: str,
    business_msisdn: str,
) -> bool:

    profile = _resolve_client_profile(db, business_msisdn)

    # ----------------------------------
    # Unknown / unconfigured bot number
    # ----------------------------------
    if not profile:
        _send_unknown_sender(db, sender, business_msisdn)
        return True

    # ----------------------------------
    # Try enabled modules
    # ----------------------------------
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

    # ----------------------------------
    # MAGEN strict handling
    # ----------------------------------
    if profile.client_code == "MAGEN":
        if is_admin_message(
            db=db,
            sender=sender,
            business_msisdn=business_msisdn,
        ):
            _send_menu(
                db=db,
                sender=sender,
                business_msisdn=business_msisdn,
                menu_key="admin_menu",
            )
            return True

        _send_magen_staff_auto_response(db, sender, business_msisdn)
        return True

    # ----------------------------------
    # Default fallback (non-MAGEN)
    # ----------------------------------
    if is_admin_message(
        db=db,
        sender=sender,
        business_msisdn=business_msisdn,
    ):
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
