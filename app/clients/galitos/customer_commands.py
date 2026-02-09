from __future__ import annotations

"""
File: app/clients/galitos/customer_commands.py
Path: app/clients/galitos/customer_commands.py
Project: KLResolute WhatsApp SaaS MVP
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text as sql_text

from app.models import Contact
from app.outbound.factory import get_meta_client

from app.menus.customer_menu_service import send_customer_menu_from_db
from app.menus.customers.galitos_food_menu import handle_galitos_menu

from app.utils.admin import is_admin_message

logger = logging.getLogger("galitos.customer_commands")


def _extract_choice_text(msg: dict) -> str:
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


def _send_customer_menu(*, db: Session, sender: str, client_id: str) -> None:
    send_customer_menu_from_db(
        db=db,
        client_id=client_id,
        sender=sender,
        menu_key="customer_menu",
    )
    logger.info("CUSTOMER_MENU_SENT | sender=%s | client_id=%s", sender, client_id)


def handle_client_command(
    *,
    db: Session,
    sender: str,
    msg: dict,
    client_id: str,
    business_msisdn: str,
) -> bool:
    msg_type = msg.get("type")

    if msg_type not in ("text", "interactive"):
        return False

    text = _extract_choice_text(msg)
    if not text:
        return False

    text_upper = text.upper()
    meta = get_meta_client(business_msisdn=business_msisdn)

    logger.info(
        "CUSTOMER_CMD_ENTER | sender=%s | text=%s | client_id=%s",
        sender,
        text_upper,
        client_id,
    )

    # FOOD FLOW
    if handle_galitos_menu(
        db=db,
        sender_number=sender,
        message_text=text,
        client_id=client_id,
    ):
        return True

    # YES / NO
    if text_upper in {"YES", "NO"}:
        state = _get_active_order_state(db, sender, client_id)
        if state and bool(state.get("order_pending")) is True:
            _close_active_order(db, sender, client_id)

            meta.send_session_message(
                to_msisdn=sender,
                text="✅ Thanks! Your Galitos order has been confirmed."
                if text_upper == "YES"
                else "❌ OK — your Galitos order was cancelled.",
            )
            return True

    # ABOUT (DB text + code emojis)
    if text_upper == "ABOUT":
        logger.info(
            "CUSTOMER_CMD_ABOUT_REQUEST | sender=%s | client_id=%s",
            sender,
            client_id,
        )

        row = (
            db.execute(
                sql_text(
                    """
                    SELECT cm.message_text
                    FROM client_messages cm
                    JOIN whatsapp_numbers w
                      ON w.client_id = cm.client_id
                    WHERE w.klresolute_client_id = :kl_client_id
                      AND w.status = 'active'
                      AND cm.message_key = 'ABOUT'
                      AND cm.is_active = TRUE
                    LIMIT 1
                    """
                ),
                {"kl_client_id": int(client_id)},
            )
            .mappings()
            .first()
        )

        if not row:
            logger.error(
                "CUSTOMER_CMD_ABOUT_MISSING | sender=%s | client_id=%s",
                sender,
                client_id,
            )
            meta.send_session_message(
                to_msisdn=sender,
                text="About information is not available at the moment.",
            )
            return True

        about_text = (
            "🔥 About Galitos\n\n"
            f"{row['message_text']}\n\n"
            "🕒 Trading Hours\n"
            "Monday – Sunday: 10:00 – 21:00\n\n"
            "📍 Location\n"
            "Visit your nearest Galitos restaurant for sit-down or takeaway.\n\n"
            "📦 What we offer\n"
            "• Flame-grilled chicken\n"
            "• Burgers, wraps & sides\n"
            "• Takeaway & dine-in\n"
            "• Daily specials\n\n"
            "Reply MENU to continue."
        )

        meta.send_session_message(
            to_msisdn=sender,
            text=about_text,
        )

        logger.info(
            "CUSTOMER_CMD_ABOUT_SENT | sender=%s | client_id=%s",
            sender,
            client_id,
        )
        return True

    # STOP
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

    # RESUME
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

    # MENU / HELP / FALLBACK
    _send_customer_menu(db=db, sender=sender, client_id=client_id)
    return True
