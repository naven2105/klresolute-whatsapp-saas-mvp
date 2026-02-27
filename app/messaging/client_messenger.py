from __future__ import annotations

"""
File: app/messaging/client_messenger.py
Path: app/messaging/client_messenger.py
Project: KLResolute WhatsApp SaaS MVP

Sprint: Full UUID Migration Hardening
+ Sprint 16 – Image Support Patch

Purpose:
Thin messaging helpers for client-facing messages.

Enhancement:
- Defensive DB rollback before outbound settings load
- Prevent aborted transaction cascade failures
- Added image message support (Sprint 16)
"""

import logging
from sqlalchemy.orm import Session
from typing import Optional, List

from app.outbound.meta import MetaWhatsAppClient
from app.outbound.settings import load_meta_settings

logger = logging.getLogger("client_messenger")


def send_message(
    *,
    db: Session,
    business_msisdn: str,
    to_number: str,
    text: str | None = None,
    template_name: str | None = None,
    template_params: Optional[List[str]] = None,
    image_id: str | None = None,        # ✅ ADDED
    caption: str | None = None,         # ✅ ADDED
    language_code: str = "en_US",
) -> None:

    logger.info(
        "SEND_MESSAGE_START | business=%s | to=%s | has_text=%s | has_template=%s | has_image=%s",
        business_msisdn,
        to_number,
        bool(text),
        bool(template_name),
        bool(image_id),
    )

    if not db:
        logger.error(
            "SEND_MESSAGE_ABORT | reason=db_missing | business=%s | to=%s",
            business_msisdn,
            to_number,
        )
        raise RuntimeError("DB session required for outbound messaging")

    if not business_msisdn:
        logger.error(
            "SEND_MESSAGE_ABORT | reason=business_msisdn_missing | to=%s",
            to_number,
        )
        raise RuntimeError("business_msisdn is required for outbound messaging")

    # -------------------------------------------------
    # UPDATED VALIDATION (extended, not replaced)
    # -------------------------------------------------

    payload_count = 0
    if text:
        payload_count += 1
    if template_name:
        payload_count += 1
    if image_id:
        payload_count += 1

    if payload_count > 1:
        logger.error(
            "SEND_MESSAGE_ABORT | reason=multiple_payload_types | business=%s | to=%s",
            business_msisdn,
            to_number,
        )
        raise ValueError("Provide only one of text, template_name, or image_id")

    if payload_count == 0:
        logger.error(
            "SEND_MESSAGE_ABORT | reason=no_payload | business=%s | to=%s",
            business_msisdn,
            to_number,
        )
        raise ValueError("Either text, template_name, or image_id must be provided")

    # -------------------------------------------------
    # Defensive rollback to clear aborted transactions
    # -------------------------------------------------
    try:
        db.rollback()
        logger.info("SEND_MESSAGE_DB_RESET | business=%s", business_msisdn)
    except Exception:
        logger.exception("SEND_MESSAGE_DB_RESET_FAIL | business=%s", business_msisdn)

    logger.info(
        "SEND_MESSAGE_SETTINGS_LOAD | business=%s",
        business_msisdn,
    )

    settings = load_meta_settings(
        db=db,
        business_msisdn=business_msisdn,
    )

    logger.info(
        "SEND_MESSAGE_SETTINGS_OK | business=%s | phone_number_id_present=%s",
        business_msisdn,
        bool(settings.phone_number_id),
    )

    meta_client = MetaWhatsAppClient(settings=settings)

    # -------------------------------------------------
    # TEXT MESSAGE (unchanged)
    # -------------------------------------------------
    if text:
        logger.info(
            "SEND_MESSAGE_EXEC | type=session | business=%s | to=%s",
            business_msisdn,
            to_number,
        )
        meta_client.send_session_message(
            to_msisdn=to_number,
            text=text,
        )
        return

    # -------------------------------------------------
    # IMAGE MESSAGE (ADDED – Sprint 16)
    # -------------------------------------------------
    if image_id:
        logger.info(
            "SEND_MESSAGE_EXEC | type=image | business=%s | to=%s",
            business_msisdn,
            to_number,
        )
        meta_client.send_image_message(
            to_msisdn=to_number,
            media_id=image_id,
            caption=caption,
        )
        return

    # -------------------------------------------------
    # TEMPLATE MESSAGE (unchanged)
    # -------------------------------------------------
    logger.info(
        "SEND_MESSAGE_EXEC | type=template | business=%s | to=%s | template=%s",
        business_msisdn,
        to_number,
        template_name,
    )

    meta_client.send_template(
        to_msisdn=to_number,
        template_name=template_name,
        language_code=language_code,
        body_params=template_params,
    )