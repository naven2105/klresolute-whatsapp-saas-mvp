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
- YES/NO only acts when awaiting food order confirmation (conversation_state.order_pending = true)
"""

from sqlalchemy.orm import Session
from sqlalchemy import text as sql_text

from app.models import Contact
from app.outbound.factory import get_meta_client

from app.menus.customers.galitos_customer_menu import GALITOS_CUSTOMER_MENU
from app.menus.customers.galitos_food_menu import handle_galitos_menu

from app.utils.admin import is_admin_message

def _render_menu(menu: dict) -> str:
    lines = [menu["title"], ""]
    for section in menu.get("sections", []):
        lines.append(section["title"])
        for cmd in section.get("commands", []):
            lines.append(cmd)
        lines.append("")
    return "\n".join(lines).strip()


def _extract_choice_text(msg: dict) -> str:
    """
    Normalise inbound message into a single 'text' value.
    Supports:
      - text.body
      - interactive.button_reply.id/title
      - interactive.list_reply.id/title
    """
    msg_type = msg.get("type")

    if msg_type == "text":
        return ((msg.get("text") or {}).get("body") or "").strip()

    if msg_type == "interactive":
        inter = msg.get("interactive") or {}

        br = inter.get("button_reply") or {}
        if br.get("id"):
            return str(br["id"]).strip()
        if br.get("title"):
            return str(br["title"]).strip()

        lr = inter.get("list_reply") or {}
        if lr.get("id"):
            return str(lr["id"]).strip()
        if lr.get("title"):
            return str(lr["title"]).strip()

    return ""


def _get_active_order_state(db: Session, sender: str, client_id: str):
    """
    Returns the active conversation_state row for this sender (if any).
    Uses the real schema you pasted.
    """
    return (
        db.execute(
            sql_text(
                """
                SELECT
                    id,
                    order_pending,
                    flavour,
                    item_sku,
                    item_name
                FROM conversation_state
                WHERE sender_msisdn = :sender
                  AND client_id = :client_id
                  AND active = TRUE
                LIMIT 1
                """
            ),
            {"sender": sender, "client_id": client_id},
        )
        .mappings()
        .first()
    )


def _close_active_order(db: Session, sender: str, client_id: str) -> None:
    """
    Closes any active order state (idempotent).
    """
    db.execute(
        sql_text(
            """
            UPDATE conversation_state
            SET
                order_pending = FALSE,
                active = FALSE,
                completed_at = now()
            WHERE sender_msisdn = :sender
              AND client_id = :client_id
              AND active = TRUE
            """
        ),
        {"sender": sender, "client_id": client_id},
    )
    db.commit()


def handle_client_command(
    *,
    db: Session,
    sender: str,
    msg: dict,
    client_id: str,
    business_msisdn: str,
) -> bool:
    msg_type = msg.get("type")

    # Accept TEXT + INTERACTIVE for Galitos (interactive is used for flavour choices)
    if msg_type not in ("text", "interactive"):
        return False

    text = _extract_choice_text(msg)
    if not text:
        return False

    text_upper = text.upper()
    meta = get_meta_client()

    # ----------------------------------
    # FOOD FLOW (must be FIRST)
    # ----------------------------------
    if handle_galitos_menu(
        db=db,
        sender_number=sender,
        message_text=text,
        client_id=client_id,
    ):
        return True

    # ----------------------------------
    # YES/NO: only when awaiting confirmation
    # ----------------------------------
    if text_upper in {"YES", "NO"}:
        state = _get_active_order_state(db, sender, client_id)

        if state and bool(state.get("order_pending")) is True:
            # Close state so repeat YES/NO doesn't loop forever
            _close_active_order(db, sender, client_id)

            if text_upper == "YES":
                meta.send_session_message(
                    to_msisdn=sender,
                    text="✅ Thanks! Your Galitos order has been confirmed.",
                )
            else:
                meta.send_session_message(
                    to_msisdn=sender,
                    text="❌ OK — your Galitos order was cancelled.",
                )
            return True

        # Standalone YES/NO falls through to menu (LOCKED requirement)

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
    if (
        text_upper == "RESUME"
        and not is_admin_message(
            db=db,
            sender=sender,
            business_msisdn=business_msisdn,
        )
    ):
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
    # FALLBACK: UNKNOWN TEXT → CUSTOMER MENU
    # ----------------------------------
    meta.send_session_message(
        to_msisdn=sender,
        text=_render_menu(GALITOS_CUSTOMER_MENU),
    )
    return True
