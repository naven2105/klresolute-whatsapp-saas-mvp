from __future__ import annotations

"""
File: app/inbound_dispatcher.py
Project: KLResolute WhatsApp SaaS MVP

LOCKED:
- No DB writes
- Behaviour defined by DB + handlers
"""

import logging
from sqlalchemy.orm import Session

from app.messaging.client_messenger import send_message
from app.profiles.client_profile import get_client_profile

from app.modules.join import handler as join_handler
from app.modules.orders import handler as orders_handler
from app.modules.inspection import handler as inspection_handler
from app.modules.survey import handler as survey_handler
from app.modules.broadcast import handler as broadcast_handler

from app.ui import emoji

logger = logging.getLogger("inbound.dispatcher")


# -------------------------------------------------
# Helpers
# -------------------------------------------------

def _reset_session(db: Session) -> None:
    try:
        db.rollback()
    except Exception:
        pass


def _render_customer_menu() -> str:
    return "\n".join(
        [
            "🍗 Welcome to Galitos!",
            "",
            "You can:",
            "📋 View this menu",
            f"{emoji.ORDER} Order a single item",
            "☎️ For multiple items, please call the store directly",
            f"{emoji.SPECIALS} View specials",
            f"{emoji.ABOUT} About (hours, address, contact)",
            f"{emoji.FEEDBACK} Send feedback",
            "",
            "Just type:",
            "ORDER",
            "SPECIALS",
            "ABOUT",
            "FEEDBACK: food was cold",
        ]
    )


def _send_customer_menu(sender: str) -> None:
    send_message(to_number=sender, text=_render_customer_menu())


# -------------------------------------------------
# Dispatcher
# -------------------------------------------------

def dispatch(*, db: Session, msg: dict, sender: str, business_msisdn: str) -> bool:
    _reset_session(db)

    profile = get_client_profile(business_msisdn, db=db)
    if not profile:
        return True

    # ----------------------------------
    # JOIN (early)
    # ----------------------------------
    if join_handler.handle(
        db=db,
        msg=msg,
        sender=sender,
        business_msisdn=business_msisdn,
    ):
        _send_customer_menu(sender)
        return True

    # ----------------------------------
    # TEXT NORMALISATION
    # ----------------------------------
    body = ""
    if msg.get("type") == "text":
        body = msg.get("text", {}).get("body", "").strip().upper()

    # ----------------------------------
    # ORDER → food menu
    # ----------------------------------
    if body == "ORDER":
        send_message(
            to_number=sender,
            text=(
                "🍗 Galitos Food Menu\n\n"
                "1️⃣ 1/2 Chicken – R89\n"
                "2️⃣ Hot Box 3 Piece + Chips – R79\n"
                "3️⃣ Full Chicken – R159\n\n"
                "Reply with the number."
            ),
        )
        return True

    # ----------------------------------
    # Orders handler (must see numeric input)
    # ----------------------------------
    if "orders" in profile.enabled_modules:
        if orders_handler.handle(
            db=db,
            msg=msg,
            sender=sender,
            business_msisdn=business_msisdn,
        ):
            return True

    # ----------------------------------
    # Other modules
    # ----------------------------------
    if "inspection" in profile.enabled_modules and inspection_handler.handle(
        db=db, msg=msg, sender=sender, business_msisdn=business_msisdn
    ):
        return True

    if "survey" in profile.enabled_modules and survey_handler.handle(
        db=db, msg=msg, sender=sender, business_msisdn=business_msisdn
    ):
        return True

    if "broadcast" in profile.enabled_modules and broadcast_handler.handle(
        db=db, msg=msg, sender=sender, business_msisdn=business_msisdn
    ):
        return True

    # ----------------------------------
    # Final fallback
    # ----------------------------------
    _send_customer_menu(sender)
    return True
