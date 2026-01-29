from __future__ import annotations

"""
File: app/inbound_dispatcher.py
Path: app/inbound_dispatcher.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Generic inbound dispatcher.
Routes inbound messages to enabled modules per client config.

Rules (LOCKED):
- No business logic
- No DB writes
- First module that handles the message wins
"""

import logging
from sqlalchemy.orm import Session

from app.clients.magen import config as magen_config
from app.clients.galitos import config as galitos_config

from app.modules.inspection import handler as inspection_handler

logger = logging.getLogger("inbound.dispatcher")

# ----------------------------------
# Client registry (explicit, MVP-safe)
# ----------------------------------

CLIENTS = {
    "27631016099": magen_config,    # MAGEN bot number
    "GALITOS_MSISDN": galitos_config,  # replace when known
}


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

    client = CLIENTS.get(business_msisdn)
    if not client:
        logger.warning(
            "DISPATCH_NO_CLIENT | business=%s | sender=%s",
            business_msisdn,
            sender,
        )
        return False

    # ----------------------------------
    # Module dispatch (ordered)
    # ----------------------------------
    for module_name in client.ENABLED_MODULES:
        if module_name == "inspection":
            handled = inspection_handler.handle(
                db=db,
                msg=msg,
                sender=sender,
                profile_code=client.INSPECTION_PROFILES["default"],
            )
            if handled:
                logger.info(
                    "MODULE_HANDLED | module=inspection | client=%s",
                    client.CLIENT_CODE,
                )
                return True

    logger.info(
        "NO_MODULE_HANDLED | client=%s | sender=%s",
        client.CLIENT_CODE,
        sender,
    )
    return True
