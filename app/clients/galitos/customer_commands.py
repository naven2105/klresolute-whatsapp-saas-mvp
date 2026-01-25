from __future__ import annotations

"""
File: app/clients/galitos/customer_commands.py

Purpose:
Galitos customer self-service command router.

Rules (LOCKED):
- FOOD → food menu
- MENU / HELP / ABOUT → customer menu
- Unknown text → customer menu
- STOP / RESUME remain functional
"""

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models import Contact
from app.outbound.factory import get_meta_client

from app.menus.customers.galitos_customer_menu import GALITOS_CUSTOMER_MENU
from app.menus.customers.galitos_food_menu import handle_galitos_menu


def _render_menu(menu: dict) -> str:
    lines = [menu["title"], ""]
    for section in menu.get("sections", []):
        lines.append(section["title"])
        for cmd in section.get("commands", []):
            lines.append(cmd)
        lines.append("")
    return "\n".join(lines).strip()


def _is_awaiting_flavour(db: Session, sender: str) -> bool:
    """
    Returns True if the last outbound Galitos message
    asked the user to choose a flavour.
    """
    row = db.execute(
        text(
            """
            SELECT 1
            FROM messages
            WHERE to_msisdn = :msisdn
              AND direction = 'OUTBOUND'
              AND content ILIKE '%flavour%'
            ORDER BY created_at DESC
            LIMIT 1
            """
        ),
        {"msisdn": sender},
    ).first()

    return bool(row)


def handle_client_command(
    *,
    db: Session,
    sender: str,
    msg: dict,
    admin_allowlist: set[str],
    client_id: str,
) -> bool:
    if msg.get("type") != "text":
        return False

    text = msg["text"]["body"].strip()
    text_upper = text.upper()
    meta = get_meta_client()

    # ----------------------------------
    # FLAVOUR SELECTION (MUST BE FIRST)
    # ----------------------------------
    if text.isdigit() and _is_awaiting_flavour(db, sender):
        # Let food handler process flavour ONLY
        handled = handle_galitos_menu(
            db=db,
            sender_number=sender,
            message_text=text,
            client_id=client_id,
        )
        return bool(handled)

    # ----------------------------------
    # FOOD MENU (item selection)
    # ----------------------------------
    if handle_galitos_menu(
        db=db,
        sender_number=sender,
        message_text=text,
        client_id=client_id,
    ):
        return True

    # ----------------------------------
    # STOP
    # ----------------------------------
    if text_upper == "STOP":
        contact = (
            db.query(Contact)
            .filter(Contact.contact_number == sender)
            .one_or_none()
        )
        if contact:
            db.delete(contact)
            db.commit()

        meta.send_generic_business_update_template(
            to_msisdn=sender,
            blob_text="You have been removed. You will no longer receive updates.",
        )
        return True

    # ----------------------------------
    # RESUME
    # ----------------------------------
    if text_upper == "RESUME" and sender not in admin_allowlist:
        existing = (
            db.query(Contact)
            .filter(Contact.contact_number == sender)
            .one_or_none()
        )
        if not existing:
            db.add(Contact(contact_number=sender))
            db.commit()

        meta.send_generic_business_update_template(
            to_msisdn=sender,
            blob_text="You have been added back. You will receive updates again.",
        )
        return True

    # ----------------------------------
    # CUSTOMER MENU (explicit)
    # ----------------------------------
    if text_upper in {"MENU", "HELP", "ABOUT"}:
        meta.send_session_message(
            to_msisdn=sender,
            text=_render_menu(GALITOS_CUSTOMER_MENU),
        )
        return True

    # ----------------------------------
    # FALLBACK
    # ----------------------------------
    meta.send_session_message(
        to_msisdn=sender,
        text=_render_menu(GALITOS_CUSTOMER_MENU),
    )
    return True
