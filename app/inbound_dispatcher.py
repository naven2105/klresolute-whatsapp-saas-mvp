from __future__ import annotations

"""
File: app/inbound_dispatcher.py
Project: KLResolute WhatsApp SaaS MVP

LOCKED:
- No DB writes
- Behaviour defined by handlers
"""

import logging
from sqlalchemy.orm import Session

from app.profiles.client_profile import get_client_profile

from app.modules.orders import handler as orders_handler
from app.modules.inspection import handler as inspection_handler
from app.modules.survey import handler as survey_handler
from app.modules.broadcast import handler as broadcast_handler

logger = logging.getLogger("inbound.dispatcher")


# -------------------------------------------------
# Helpers
# -------------------------------------------------

def _reset_session(db: Session) -> None:
    try:
        db.rollback()
    except Exception:
        pass


# -------------------------------------------------
# Dispatcher
# -------------------------------------------------

def dispatch(*, db: Session, msg: dict, sender: str, business_msisdn: str) -> bool:
    _reset_session(db)

    profile = get_client_profile(business_msisdn, db=db)
    if not profile:
        return True

    # ----------------------------------
    # ORDERS (Galitos only)
    # ----------------------------------
    if profile.client_code == "GALITOS" and "orders" in profile.enabled_modules:
        if orders_handler.handle(
            db=db,
            msg=msg,
            sender=sender,
            business_msisdn=business_msisdn,
        ):
            return True

    # ----------------------------------
    # INSPECTION (non-Galitos only)
    # ----------------------------------
    if profile.client_code != "GALITOS" and "inspection" in profile.enabled_modules:
        if inspection_handler.handle(
            db=db,
            msg=msg,
            sender=sender,
            profile_code=profile.client_code,
        ):
            return True

    # ----------------------------------
    # Other modules
    # ----------------------------------
    if "survey" in profile.enabled_modules and survey_handler.handle(
        db=db,
        msg=msg,
        sender=sender,
        business_msisdn=business_msisdn,
    ):
        return True

    if "broadcast" in profile.enabled_modules and broadcast_handler.handle(
        db=db,
        msg=msg,
        sender=sender,
        business_msisdn=business_msisdn,
    ):
        return True

    # Final fallback handled by Tier-1 router
    return False
