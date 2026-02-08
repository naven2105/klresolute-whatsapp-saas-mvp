from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.services.order_service import create_order, OrderCreate
from app.services.galitos_staff_notifier import notify_galitos_staff
from app.outbound.meta import MetaWhatsAppClient
from app.outbound.settings import load_meta_settings

logger = logging.getLogger("galitos_order_handler")

_meta_client = MetaWhatsAppClient(settings=load_meta_settings())


def _send_text(to_number: str, text: str) -> None:
    logger.info("ORDER_SEND_TEXT | to=%s | text=%r", to_number, text)
    _meta_client.send_session_message(
        to_msisdn=to_number,
        text=text,
    )


def handle_order_message(
    *,
    db: Session,
    from_number: str,
    text: str,
    context: Dict[str, Any],
) -> bool:

    logger.info(
        "ORDER_HANDLER_ENTER | sender=%s | text=%r",
        from_number,
        text,
    )

    state = db.execute(
        text(
            """
            SELECT *
            FROM conversation_state
            WHERE sender_msisdn = :sender
              AND active = true
              AND state_type = 'ORDER'
            ORDER BY started_at DESC
            LIMIT 1
            """
        ),
        {"sender": from_number},
    ).mappings().first()

    if not state:
        logger.info(
            "ORDER_HANDLER_EXIT | reason=no_active_state | sender=%s",
            from_number,
        )
        return False

    normalized = (text or "").strip().upper()

    if normalized == "YES":
        order = OrderCreate(
            client_id=state["client_id"],
            customer_msisdn=from_number,
            item_sku=state["item_sku"],
            item_name=state["item_name"],
            flavour=state["flavour"],
            base_price=state["base_price"],
            drink_addon=state["drink_addon"],
            addon_price=state["addon_price"],
            total_amount=state["total_amount"],
        )
        create_order(db, order)

        db.execute(
            text(
                """
                UPDATE conversation_state
                SET active = false,
                    completed_at = now()
                WHERE id = :id
                """
            ),
            {"id": state["id"]},
        )
        db.commit()

        now = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=2)))
        timestamp = now.strftime("%A, %Y-%m-%d · %Hh%M")

        flavour_label = (
            "Hot" if state["flavour"] == "H"
            else "Mild" if state["flavour"] == "M"
            else "Lemon & Herb"
        )

        staff_message = (
            f"New Galitos Order | {timestamp} | "
            f"Item: {state['item_name']} | "
            f"Flavour: {flavour_label} | "
            f"Total: R{state['total_amount']} | "
            f"Customer: {from_number}"
        )

        notify_galitos_staff(
            db=db,
            client_id=state["client_id"],
            message=staff_message,
        )

        _send_text(
            from_number,
            "✅ Thank you! Your order has been received.\n\n"
            "Type MENU to order again."
        )
        return True

    _send_text(from_number, "Reply YES to confirm or NO to cancel.")
    return True
