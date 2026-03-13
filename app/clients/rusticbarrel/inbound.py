# ==================================================
# File: inbound.py
# Path: app/clients/rusticbarrel/inbound.py
# Project: KLResolute WhatsApp SaaS MVP
#
# Sprint 34 – RusticBarrel Tenant Alignment
#
# Update:
# - Structured menu system removed (Sprint 34).
#   Food menu handled via image menu system.
# ==================================================

from __future__ import annotations

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.messaging.client_messenger import send_message
from app.clients.rusticbarrel.customer.booking_service import handle_booking_command
from app.clients.rusticbarrel.customer.main_menu_service import handle_main_menu

from app.clients.rusticbarrel.handlers.campaign_handler import handle_admin_message
from app.clients.rusticbarrel.survey.survey_handler import handle_survey_command
from app.clients.rusticbarrel.admin.admin_menu_service import handle_admin_menu
from app.clients.rusticbarrel.admin.admin_router import route_admin_message

logger = logging.getLogger("rusticbarrel.inbound")


WELCOME_MESSAGE = (
    "Welcome to Rustic Barrel 🍗🔥\n"
    "You can:\n"
    "• Type menu to see options\n"
    "• Type food to see food menu\n"
    "• Type book to reserve a table\n"
    "Reply STOP anytime to unsubscribe."
)

STOP_CONFIRMATION = (
    "You have been unsubscribed from marketing messages.\n"
    "You can still use menu and booking anytime."
)

ABOUT_MESSAGE = (
    "🍗 About RusticBarrel\n\n"
    "Rustic Barrel Pub and Grill is your local spot for tasty food.\n"
    "We look forward to hosting you!"
)


def handle_rusticbarrel_inbound(
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
    msg_lower = msg.lower()

    try:

        # --------------------------------------------------
        # ROLE DETECTION
        # --------------------------------------------------
        role = "customer"

        if db.execute(
            text(
                "SELECT 1 FROM r_rusticbarrel__staff WHERE msisdn = :phone AND role = 'admin' LIMIT 1"
            ),
            {"phone": sender_msisdn},
        ).fetchone():
            role = "admin"

        elif db.execute(
            text("SELECT 1 FROM r_rusticbarrel__staff WHERE msisdn = :phone LIMIT 1"),
            {"phone": sender_msisdn},
        ).fetchone():
            role = "staff"

        # --------------------------------------------------
        # ADMIN COMMANDS
        # --------------------------------------------------
        if role == "admin":
            return route_admin_message(
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
        # CUSTOMER
        # --------------------------------------------------

        if msg_lower in ("stop", "unsubscribe"):
            db.execute(
                text(
                    """
                    UPDATE r_rusticbarrel__customers
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

        # Auto register
        result = db.execute(
            text(
                """
                INSERT INTO r_rusticbarrel__customers (phone)
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
        # MAIN MENU
        # --------------------------------------------------
        if msg_lower == "menu":
            return handle_main_menu(
                db=db,
                sender_msisdn=sender_msisdn,
                business_msisdn=business_msisdn,
                message_text=msg,
            )

        if msg_lower == "about":
            send_message(
                db=db,
                business_msisdn=business_msisdn,
                to_number=sender_msisdn,
                text=ABOUT_MESSAGE,
            )
            return True

        if handle_booking_command(
            db=db,
            sender_msisdn=sender_msisdn,
            business_msisdn=business_msisdn,
            message_text=msg,
        ):
            return True

        if msg_lower in ("announcement", "special", "specials"):
            result = db.execute(
                text(
                    """
                    SELECT type, message, image_url
                    FROM r_rusticbarrel__campaigns
                    ORDER BY sent_at DESC
                    LIMIT 1
                    """
                )
            ).fetchone()

            if not result:
                send_message(
                    db=db,
                    business_msisdn=business_msisdn,
                    to_number=sender_msisdn,
                    text="No active specials at the moment.",
                )
                return True

            if result.type == "text":
                send_message(
                    db=db,
                    business_msisdn=business_msisdn,
                    to_number=sender_msisdn,
                    text=f"📢 Rustic Barrel Announcement\n\n{result.message}",
                )
            else:
                send_message(
                    db=db,
                    business_msisdn=business_msisdn,
                    to_number=sender_msisdn,
                    image_id=result.image_url,
                    caption=result.message,
                )

            return True

    except SQLAlchemyError:
        db.rollback()
        logger.exception("RUSTICBARREL_DB_ERROR")
        return True

    except Exception:
        db.rollback()
        logger.exception("RUSTICBARREL_UNEXPECTED_ERROR")
        return True

    return handle_main_menu(
        db=db,
        sender_msisdn=sender_msisdn,
        business_msisdn=business_msisdn,
        message_text=msg,
    )