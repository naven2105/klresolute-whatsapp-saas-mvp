from __future__ import annotations

"""
File: app/client/commands.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Customer self-service commands + menu routing.

LOCKED RULES:
- Renders CUSTOMER menus only
- FOOD routes to food menu handler
- Unknown text → CUSTOMER menu
"""

import logging
from sqlalchemy.orm import Session

from app.models import Contact
from app.outbound.factory import get_meta_client
from app.menus.customers.galitos_customer_menu import GALITOS_CUSTOMER_MENU
from app.menus.customers.galitos_food_menu import handle_galitos_menu

logger = logging.getLogger("client_commands")


def _render_menu(menu: dict) -> str:
    logger.info("RENDER_MENU")
    lines = [menu["title"], ""]
    for section in menu.get("sections", []):
        lines.append(section["title"])
        for cmd in section.get("commands", []):
            lines.append(cmd)
        lines.append("")
    return "\n".join(lines).strip()


def handle_client_command(
    *,
    db: Session,
    sender: str,
    msg: dict,
    admin_allowlist: set[str],
    client_id: str,
) -> bool:
    logger.info(
        "ENTER | sender=%s | msg_type=%s",
        sender,
        msg.get("type"),
    )

    try:
        if msg.get("type") != "text":
            logger.info("EXIT | non-text message")
            return False

        text = msg["text"]["body"].strip()
        text_upper = text.upper()
        meta = get_meta_client()

        logger.info(
            "TEXT | sender=%s | text=%r",
            sender,
            text,
        )

        # -------------------------------
        # FOOD MENU (must be FIRST)
        # -------------------------------
        if handle_galitos_menu(
            db=db,
            sender_number=sender,
            message_text=text,
            client_id=client_id,
        ):
            logger.info("FOOD_MENU_HANDLED | sender=%s", sender)
            return True

        # -------- STOP --------
        if text_upper == "STOP":
            logger.info("STOP_REQUEST | sender=%s", sender)
            contact = db.query(Contact).filter(
                Contact.contact_number == sender
            ).one_or_none()
            if contact:
                db.delete(contact)
                db.commit()
                logger.info("CONTACT_REMOVED | sender=%s", sender)

            meta.send_generic_business_update_template(
                to_msisdn=sender,
                blob_text="You have been removed. You will no longer receive updates.",
            )
            return True

        # -------- RESUME --------
        if text_upper == "RESUME" and sender not in admin_allowlist:
            logger.info("RESUME_REQUEST | sender=%s", sender)
            existing = db.query(Contact).filter(
                Contact.contact_number == sender
            ).one_or_none()
            if not existing:
                db.add(Contact(contact_number=sender))
                db.commit()
                logger.info("CONTACT_ADDED | sender=%s", sender)

            meta.send_generic_business_update_template(
                to_msisdn=sender,
                blob_text="You have been added back. You will receive updates again.",
            )
            return True

        # -------- CUSTOMER MENU --------
        if text_upper in {"MENU", "HELP", "ABOUT"}:
            logger.info("CUSTOMER_MENU_REQUEST | sender=%s", sender)
            meta.send_session_message(
                to_msisdn=sender,
                text=_render_menu(GALITOS_CUSTOMER_MENU),
            )
            return True

        # -------- UNKNOWN → MENU --------
        logger.warning(
            "UNKNOWN_CUSTOMER_INPUT | sender=%s | text=%r",
            sender,
            text,
        )
        meta.send_session_message(
            to_msisdn=sender,
            text=_render_menu(GALITOS_CUSTOMER_MENU),
        )
        return True

    except Exception:
        logger.exception(
            "ERROR | client_commands | sender=%s | text=%r",
            sender,
            msg,
        )
        raise
