from __future__ import annotations

"""
File: app/outbound/settings.py
Path: app/outbound/settings.py
Project: KLResolute WhatsApp SaaS MVP

SPRINT: UUID Identity Consolidation (STRICT MODE)

Purpose:
- Centralised outbound (Meta WhatsApp Cloud API) configuration.
- Resolve Meta sender identity strictly from DB.
- No ENV phone_number_id fallback allowed.

Rules:
- META_WA_ACCESS_TOKEN required
- db + business_msisdn required
- Fail fast if sender identity missing
"""

import os
import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger("outbound.settings")


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            f"Set it in your environment."
        )
    return value


@dataclass(frozen=True)
class MetaWhatsAppSettings:
    api_version: str
    access_token: str
    phone_number_id: str

    @property
    def base_url(self) -> str:
        return f"https://graph.facebook.com/{self.api_version}"

    @property
    def messages_url(self) -> str:
        return f"{self.base_url}/{self.phone_number_id}/messages"


def _load_phone_number_id_from_db(
    *,
    db: Session,
    business_msisdn: str,
) -> Optional[str]:
    try:
        row = (
            db.execute(
                text(
                    """
                    SELECT c.meta_phone_number_id
                    FROM whatsapp_numbers w
                    JOIN clients c
                      ON c.client_id = w.client_id
                    WHERE w.destination_number = :business
                      AND w.status = 'active'
                    LIMIT 1
                    """
                ),
                {"business": business_msisdn},
            )
            .mappings()
            .first()
        )

        if not row:
            return None

        meta_phone_number_id = row.get("meta_phone_number_id")
        if not meta_phone_number_id:
            return None

        return str(meta_phone_number_id).strip()

    except Exception:
        logger.exception(
            "META_SENDER_LOOKUP_FAIL | business=%s",
            business_msisdn,
        )
        return None


def load_meta_settings(
    *,
    db: Session,
    business_msisdn: str,
) -> MetaWhatsAppSettings:

    if not db:
        raise RuntimeError("DB session required for Meta settings")

    if not business_msisdn:
        raise RuntimeError("business_msisdn required for Meta settings")

    api_version = os.getenv("META_WA_API_VERSION", "v20.0").strip()
    access_token = _require_env("META_WA_ACCESS_TOKEN")

    phone_number_id = _load_phone_number_id_from_db(
        db=db,
        business_msisdn=business_msisdn,
    )

    if not phone_number_id:
        raise RuntimeError(
            "Missing Meta sender identity in DB. "
            "Ensure clients.meta_phone_number_id is populated and whatsapp_numbers mapping is active."
        )

    return MetaWhatsAppSettings(
        api_version=api_version,
        access_token=access_token,
        phone_number_id=phone_number_id,
    )
