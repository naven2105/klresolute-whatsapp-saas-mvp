from __future__ import annotations

"""
File: app/inbound_dispatcher.py
Path: app/inbound_dispatcher.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Generic inbound dispatcher.
Routes inbound messages to enabled modules per client profile.

Rules (LOCKED):
- No business logic
- No DB writes
- First module that handles the message wins
"""

import logging
from sqlalchemy.orm import Session

from app.profiles.client_profile import get_client_profile

# ---- Modules ----
from app.modules.inspection import handler as inspection_handler
from app.modules.vehicle_inspection import handler as vehicle_inspection_handler
from app.modules.survey import handler as survey_handler
from app.modules.broadcast import handler as broadcast_handler
from app.modules.orders import handler as orders_handler

logger = logging.getLogger("inbound.dispatcher")


def dispatch(
    *,
    db: Session,
    msg: dict,
    sender: str,
    business_msisdn: str,
) -> bool:
    """
    Dispatch inbound message to enabled modules for the client.
    """

    profile = get_client_profile(business_msisdn)
    if not profile:
        logger.warning(
            "DISPATCH_NO_PROFILE | business=%s | sender=%s",
            business_msisdn,
            sender,
        )
        return False

    # ----------------------------------
    # Module dispatch (ORDER MATTERS)
    # ----------------------------------
    for module in profile.enabled_modules:

        if module == "orders":
            if orders_handler.handle(
                db=db,
                msg=msg,
                sender=sender,
                business_msisdn=business_msisdn,
            ):
                logger.info("MODULE_HANDLED | orders | %s", profile.client_code)
                return True

        if module == "inspection":
            if inspection_handler.handle(
                db=db,
                msg=msg,
                sender=sender,
                business_msisdn=business_msisdn,
            ):
                logger.info("MODULE_HANDLED | inspection | %s", profile.client_code)
                return True

        if module == "vehicle_inspection":
            if vehicle_inspection_handler.handle(
                db=db,
                msg=msg,
                sender=sender,
                business_msisdn=business_msisdn,
            ):
                logger.info("MODULE_HANDLED | vehicle_inspection | %s", profile.client_code)
                return True

        if module == "survey":
            if survey_handler.handle(
                db=db,
                msg=msg,
                sender=sender,
                business_msisdn=business_msisdn,
            ):
                logger.info("MODULE_HANDLED | survey | %s", profile.client_code)
                return True

        if module == "broadcast":
            if broadcast_handler.handle(
                db=db,
                msg=msg,
                sender=sender,
                business_msisdn=business_msisdn,
            ):
                logger.info("MODULE_HANDLED | broadcast | %s", profile.client_code)
                return True

    logger.info(
        "NO_MODULE_HANDLED | client=%s | sender=%s",
        profile.client_code,
        sender,
    )
    return True
