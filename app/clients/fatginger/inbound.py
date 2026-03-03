# ==================================================
# File: inbound.py
# Path: app/clients/fatginger/inbound.py
# Project: KLResolute WhatsApp SaaS MVP
# ==================================================

from __future__ import annotations

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.messaging.client_messenger import send_message
from app.clients.fatginger.customer.booking_service import handle_booking_command
from app.clients.fatginger.customer.menu_service import (
    handle_menu_command,
    handle_drinks_command,
)
from app.clients.fatginger.customer.main_menu_service import (
    handle_main_menu,
)
from app.clients.fatginger.feedback.handler import (
    handle_feedback_message,
)
from app.clients.fatginger.handlers.campaign_handler import (
    handle_admin_message,
)

logger = logging.getLogger("fatginger.inbound")


WELCOME_MESSAGE = (
    "Welcome to FatGinger 🍔🔥\n"
    "You can:\n"
    "• Type menu to see options\n"
    "• Type food to see food menu\n"
    "• Type drinks to see beverages\n"
    "• Type book to reserve a table\n"
    "Reply STOP anytime to unsubscribe."
)

STOP_CONFIRMATION = (
    "You have been unsubscribed from marketing messages.\n"
    "You can still use menu and booking anytime."
)


def handle_fatginger_inbound(
    db: Session,
    sender_msisdn: str,
    business_msisdn: str,
    message_text: str | None,
    message_type: str,
    media_url: str | None,
) -> bool:

    if not message_text and message_type != "image":
        return False

    msg = (message_text or "").strip()

    try:

        # --------------------------------------------------
        # ROLE DETECTION
        # --------------------------------------------------
        role = "customer"

        if db.execute(
            text("SELECT 1 FROM r_fg__admins WHERE msisdn = :phone LIMIT 1"),
            {"phone": sender_msisdn},
        ).fetchone():
            role = "admin"

        elif db.execute(
            text("SELECT 1 FROM r_fg__staff WHERE msisdn = :phone LIMIT 1"),
            {"phone": sender_msisdn},
        ).fetchone():
            role = "staff"

        # --------------------------------------------------
        # ADMIN
        # --------------------------------------------------
        if role == "admin":
            return handle_admin_message(
                db=db,
                sender_msisdn=sender_msisdn,
                business_msisdn=business_msisdn,
                message_text=message_text,
                message_type=message_type,
                media_url=media_url,
            )

        # --------------------------------------------------
        # STAFF
        # --------------------------------------------------
        if role == "staff":
            return True

        # --------------------------------------------------
        # CUSTOMER LOGIC
        # --------------------------------------------------

        lower_msg = msg.lower()

        if lower_msg in ("stop", "leave", "unsubscribe"):
            db.execute(
                text(
                    """
                    UPDATE r_fg__customers
                    SET marketing_opt_in = FALSE,
                        opt_out_timestamp = NOW()
                    WHERE phone = :phone
                    """
                ),
                {"phone": sender_msisdn},
            )
            db.commit()

            send_message(
                db=db,
                business_msisdn=business_msisdn,
                to_number=sender_msisdn,
                text=STOP_CONFIRMATION,
            )
            return True

        result = db.execute(
            text(
                """
                INSERT INTO r_fg__customers (phone)
                VALUES (:phone)
                ON CONFLICT (phone) DO NOTHING
                """
            ),
            {"phone": sender_msisdn},
        )
        db.commit()

        if result.rowcount == 1:
            send_message(
                db=db,
                business_msisdn=business_msisdn,
                to_number=sender_msisdn,
                text=WELCOME_MESSAGE,
            )

        # --------------------------------------------------
        # FEEDBACK (before booking)
        # --------------------------------------------------
        if handle_feedback_message(
            db=db,
            sender_number=sender_msisdn,
            message_text=message_text,
            media_id=media_url,
            media_type=message_type,
            business_msisdn=business_msisdn,
        ):
            return True

        # --------------------------------------------------
        # BOOKING
        # --------------------------------------------------
        if handle_booking_command(
            db=db,
            sender_msisdn=sender_msisdn,
            business_msisdn=business_msisdn,
            message_text=msg,
        ):
            return True

        # --------------------------------------------------
        # FOOD
        # --------------------------------------------------
        if handle_menu_command(
            db=db,
            sender_msisdn=sender_msisdn,
            business_msisdn=business_msisdn,
            message_text=msg,
        ):
            return True

        # --------------------------------------------------
        # DRINKS
        # --------------------------------------------------
        if handle_drinks_command(
            db=db,
            sender_msisdn=sender_msisdn,
            business_msisdn=business_msisdn,
            message_text=msg,
        ):
            return True

        # --------------------------------------------------
        # MAIN MENU (fallback)
        # --------------------------------------------------
        return handle_main_menu(
            db=db,
            sender_msisdn=sender_msisdn,
            business_msisdn=business_msisdn,
            message_text=msg,
        )

    except SQLAlchemyError:
        db.rollback()
        logger.exception("FG_DB_ERROR")
        return True

    except Exception:
        db.rollback()
        logger.exception("FG_UNEXPECTED_ERROR")
        return True