from __future__ import annotations

"""
File: app/outbound/settings.py
Path: app/outbound/settings.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
- Centralised outbound (Meta WhatsApp Cloud API) configuration.
- Keep secrets out of code via environment variables.
- Resolve Meta sender identity (phone_number_id) per client/business when provided.

Notes:
- Required for sending:
  - META_WA_ACCESS_TOKEN
  - META_WA_PHONE_NUMBER_ID (legacy fallback only; prefer DB per-client meta_phone_number_id)
- Optional:
  - META_WA_API_VERSION (defaults to v20.0 if not provided)
"""

import os
import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import text

# ==================================================
# Logging
# ==================================================
logger = logging.getLogger("outbound.settings")


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            f"Set it in your .env / Render / shell before running."
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
        logger.info(
            "META_SENDER_LOOKUP_START | check=business_to_client_meta | business=%s",
            business_msisdn,
        )

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
            logger.error(
                "META_SENDER_LOOKUP_MISS | reason=no_active_whatsapp_number_mapping | business=%s",
                business_msisdn,
            )
            return None

        meta_phone_number_id = row.get("meta_phone_number_id")

        if not meta_phone_number_id:
            logger.error(
                "META_SENDER_LOOKUP_MISS | reason=meta_phone_number_id_null_or_empty | business=%s",
                business_msisdn,
            )
            return None

        logger.info(
            "META_SENDER_LOOKUP_OK | business=%s | meta_phone_number_id_present=%s",
            business_msisdn,
            True,
        )
        return str(meta_phone_number_id).strip()

    except Exception:
        logger.exception(
            "META_SENDER_LOOKUP_FAIL | business=%s",
            business_msisdn,
        )
        return None


def load_meta_settings(
    *,
    db: Optional[Session] = None,
    business_msisdn: Optional[str] = None,
) -> MetaWhatsAppSettings:
    api_version = os.getenv("META_WA_API_VERSION", "v20.0").strip()
    access_token = _require_env("META_WA_ACCESS_TOKEN")

    if db is not None and business_msisdn:
        phone_number_id = _load_phone_number_id_from_db(
            db=db,
            business_msisdn=business_msisdn,
        )
        if not phone_number_id:
            logger.error(
                "META_SETTINGS_ABORT | reason=missing_sender_identity | business=%s | continued=%s",
                business_msisdn,
                False,
            )
            raise RuntimeError(
                "Missing Meta sender identity for business. "
                "Ensure clients.meta_phone_number_id is populated and whatsapp_numbers mapping is active."
            )

        logger.info(
            "META_SETTINGS_DB_SENDER | business=%s | api_version=%s",
            business_msisdn,
            api_version,
        )
        return MetaWhatsAppSettings(
            api_version=api_version,
            access_token=access_token,
            phone_number_id=phone_number_id,
        )

    logger.warning(
        "META_SETTINGS_ENV_SENDER | check=db_and_business_required | db_provided=%s | business_provided=%s | continued=%s",
        bool(db is not None),
        bool(business_msisdn),
        True,
    )

    return MetaWhatsAppSettings(
        api_version=api_version,
        access_token=access_token,
        phone_number_id=_require_env("META_WA_PHONE_NUMBER_ID"),
    )
