# ==================================================
# File: inbound.py
# Path: app/clients/periperi/inbound.py
# Project: KLResolute WhatsApp SaaS MVP
#
# Patch:
# - Fix Lite AI category matching (LIKE instead of =)
# ==================================================

from __future__ import annotations

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.messaging.client_messenger import send_message
from app.clients.periperi.customer.booking_service import handle_booking_command
from app.clients.periperi.customer.main_menu_service import handle_main_menu
from app.clients.periperi.customer.menu_service import handle_menu_command
from app.clients.periperi.handlers.campaign_handler import handle_admin_message
from app.clients.periperi.survey.survey_handler import handle_survey_command
from app.clients.periperi.admin.admin_router import route_admin_message

logger = logging.getLogger("periperi.inbound")


WELCOME_MESSAGE = (
    "🐔 Welcome to O' Peri Peri Edenvale!\n\n"
    "Ask anything or type menu to get started 😊"
)

STOP_CONFIRMATION = (
    "You have been unsubscribed from marketing messages.\n"
    "You can still use menu and booking anytime."
)

ABOUT_MESSAGE = (
    "🐔 About O' Peri Peri Edenvale\n\n"
    "Authentic Portuguese cuisine with flame-grilled peri-peri flavours."
)

# --------------------------------------------------
# LITE AI CONFIG
# --------------------------------------------------

KEYWORD_MAP = {
    "prawn": "Seafood",
    "prawns": "Seafood",
    "fish": "Seafood",
    "calamari": "Seafood",
    "spicy": "Chicken",
    "chicken": "Chicken",
    "burger": "Burgers",
    "roll": "Burgers",
    "steak": "Grills",
    "rump": "Grills",
    "pizza": "Pizza",
    "pasta": "Pasta",
    "salad": "Salads",
    "combo": "Combos",
    "ribs": "Grills",
}


def handle_lite_ai_fallback(
    db: Session,
    sender_msisdn: str,
    business_msisdn: str,
    message_text: str,
) -> bool:

    msg_lower = message_text.lower()

    matched_category = None

    for keyword, category in KEYWORD_MAP.items():
        if keyword in msg_lower:
            matched_category = category
            break

    # fallback intent
    if not matched_category:
        if "food" in msg_lower or "eat" in msg_lower or "recommend" in msg_lower:
            matched_category = "Chicken"

    if not matched_category:
        return False

    # 🔥 FIXED QUERY (LIKE instead of =)
    items = db.execute(
        text(
            """
            SELECT name, price
            FROM r_periperi__menu_items
            WHERE LOWER(category) LIKE LOWER(:category)
            LIMIT 3
            """
        ),
        {"category": f"%{matched_category}%"},
    ).fetchall()

    if not items:
        return False

    lines = [f"• {i.name} - R{i.price}" for i in items]

    response = (
        f"🔥 Yes we do! Here are some {matched_category.lower()} options:\n\n"
        + "\n".join(lines)
        + "\n\nType menu to view full menu or specials for deals."
    )

    send_message(
        db=db,
        business_msisdn=business_msisdn,
        to_number=sender_msisdn,
        text=response,
    )

    return True


# --------------------------------------------------
# MAIN HANDLER
# --------------------------------------------------

def handle_periperi_inbound(
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

        # ROLE DETECTION
        role = "customer"

        if db.execute(
            text("SELECT 1 FROM r_periperi__staff WHERE msisdn = :phone AND role = 'admin' LIMIT 1"),
            {"phone": sender_msisdn},
        ).fetchone():
            role = "admin"

        elif db.execute(
            text("SELECT 1 FROM r_periperi__staff WHERE msisdn = :phone LIMIT 1"),
            {"phone": sender_msisdn},
        ).fetchone():
            role = "staff"

        # ADMIN
        if role == "admin":
            return route_admin_message(
                db=db,
                sender_msisdn=sender_msisdn,
                business_msisdn=business_msisdn,
                message_text=message_text,
                message_type=message_type,
                media_url=media_url,
            )

        # STAFF
        if role == "staff":
            return True

        # STOP
        if msg_lower in ("stop", "unsubscribe"):
            db.execute(
                text(
                    """
                    UPDATE r_periperi__customers
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

        # REGISTER
        result = db.execute(
            text(
                """
                INSERT INTO r_periperi__customers (phone)
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

        # MENU
        if msg_lower == "menu":
            return handle_main_menu(
                db=db,
                sender_msisdn=sender_msisdn,
                business_msisdn=business_msisdn,
                message_text=msg,
            )

        # FOOD MENU
        if handle_menu_command(
            db=db,
            sender_msisdn=sender_msisdn,
            business_msisdn=business_msisdn,
            message_text=msg,
        ):
            return True

        # ABOUT
        if msg_lower == "about":
            send_message(
                db=db,
                business_msisdn=business_msisdn,
                to_number=sender_msisdn,
                text=ABOUT_MESSAGE,
            )
            return True

        # BOOKING
        if handle_booking_command(
            db=db,
            sender_msisdn=sender_msisdn,
            business_msisdn=business_msisdn,
            message_text=msg,
        ):
            return True

        # SPECIALS
        if msg_lower in ("announcement", "special", "specials"):
            result = db.execute(
                text(
                    """
                    SELECT type, message, image_url
                    FROM r_periperi__campaigns
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
                    text=f"📢 O' Peri Peri Special\n\n{result.message}",
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

        # 🔥 LITE AI
        if handle_lite_ai_fallback(
            db=db,
            sender_msisdn=sender_msisdn,
            business_msisdn=business_msisdn,
            message_text=msg,
        ):
            return True

    except SQLAlchemyError:
        db.rollback()
        logger.exception("PP_DB_ERROR")
        return True

    except Exception:
        db.rollback()
        logger.exception("PP_UNEXPECTED_ERROR")
        return True

    # FINAL FALLBACK
    return handle_main_menu(
        db=db,
        sender_msisdn=sender_msisdn,
        business_msisdn=business_msisdn,
        message_text=msg,
    )