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
from app.modules.inspection import handler as inspection_handler
from app.modules.survey import handler as survey_handler
from app.modules.broadcast import handler as broadcast_handler
from app.modules.orders import handler as orders_handler

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
    # IMPORTANT:
    # - Use only emojis that are guaranteed to exist in emoji.py
    # - Any additional emojis are literal strings here (safe in Python source)
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
            "Just type one of these:",
            "MENU",
            "ORDER",
            "SPECIALS",
            "ABOUT",
            "FEEDBACK: food was cold",
        ]
    )


def _send_customer_menu(sender: str) -> None:
    send_message(
        to_number=sender,
        text=_render_customer_menu(),
    )


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
    # Text normalisation for routing
    # ----------------------------------
    body = ""
    if msg.get("type") == "text":
        body = msg.get("text", {}).get("body", "").strip().upper()

    # ----------------------------------
    # ORDER → order flow (food menu)
    # ----------------------------------
    if body == "ORDER":
        if orders_handler.handle(
            db=db,
            msg=msg,
            sender=sender,
            business_msisdn=business_msisdn,
        ):
            return True

    # ----------------------------------
    # Other enabled modules (excluding orders which is routed above)
    # ----------------------------------
    for module in profile.enabled_modules:
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
    # MENU / HELP / unknown → customer menu
    # ----------------------------------
    _send_customer_menu(sender)
    return True
