from __future__ import annotations

"""
File: app/outbound/factory.py
Path: app/outbound/factory.py
Project: KLResolute WhatsApp SaaS MVP

SPRINT: UUID Identity Consolidation

Purpose:
- Construct and reuse outbound Meta WhatsApp clients
- One client per business (WABA)
- Sender identity MUST be resolved from DB
- ENV phone_number_id fallback REMOVED

Rules:
- business_msisdn is mandatory
- db session is mandatory
- Fail fast if sender identity missing
"""

import logging
from typing import Dict
from sqlalchemy.orm import Session

from app.outbound.meta import MetaWhatsAppClient
from app.outbound.settings import load_meta_settings

logger = logging.getLogger("outbound.factory")

_meta_clients: Dict[str, MetaWhatsAppClient] = {}


def get_meta_client(
    *,
    db: Session,
    business_msisdn: str,
) -> MetaWhatsAppClient:
    """
    Return a MetaWhatsAppClient scoped to a business.

    Requirements:
    - db session required
    - business_msisdn required
    - Sender identity resolved from DB via load_meta_settings
    """

    if not db:
        logger.error("META_FACTORY_ABORT | reason=db_missing")
        raise RuntimeError("DB session required for Meta client")

    if not business_msisdn:
        logger.error("META_FACTORY_ABORT | reason=business_missing")
        raise RuntimeError("business_msisdn required for Meta client")

    key = business_msisdn

    if key not in _meta_clients:
        logger.info(
            "META_FACTORY_BUILD_START | business=%s",
            business_msisdn,
        )

        settings = load_meta_settings(
            db=db,
            business_msisdn=business_msisdn,
        )

        _meta_clients[key] = MetaWhatsAppClient(settings=settings)

        logger.info(
            "META_FACTORY_BUILD_OK | business=%s",
            business_msisdn,
        )

    return _meta_clients[key]
