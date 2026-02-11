from __future__ import annotations

"""
File: app/messaging/transport.py
Path: app/messaging/transport.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Outbound transport boundary for WhatsApp messaging.

LOCKED RULES:
- Only this file may call MetaWhatsAppClient.
- No business logic.
- Defensive guards required.
- Explicit logging of success + failure.
"""

import logging
from typing import Sequence

from app.outbound.meta import MetaWhatsAppClient, MetaSendResult
from app.outbound.settings import load_meta_settings

logger = logging.getLogger("transport")

_meta_client = MetaWhatsAppClient(settings=load_meta_settings())


# -------------------------------------------------
# Internal Guard
# -------------------------------------------------

def _validate_msisdn(msisdn: str) -> None:
    if not msisdn:
        raise ValueError("MSISDN cannot be empty")

    if not msisdn.isdigit():
        raise ValueError(f"MSISDN must be numeric: {msisdn}")

    if len(msisdn) < 10:
        raise ValueError(f"MSISDN too short: {msisdn}")


# -------------------------------------------------
# Public Transport Methods
# -------------------------------------------------

def send_session(
    *,
    to_msisdn: str,
    text: str,
) -> MetaSendResult:

    _validate_msisdn(to_msisdn)

    if not text:
        raise ValueError("Session message text cannot be empty")

    logger.info(
        "TRANSPORT_SEND_SESSION_ENTER | to=%s | text_len=%s",
        to_msisdn,
        len(text),
    )

    try:
        result = _meta_client.send_session_message(
            to_msisdn=to_msisdn,
            text=text,
        )

        logger.info(
            "TRANSPORT_SEND_SESSION_SUCCESS | to=%s | message_id=%s",
            to_msisdn,
            getattr(result, "message_id", None),
        )

        return result

    except Exception:
        logger.exception(
            "TRANSPORT_SEND_SESSION_FAIL | to=%s",
            to_msisdn,
        )
        raise


def send_template(
    *,
    to_msisdn: str,
    template_name: str,
    language_code: str,
    body_params: Sequence[str] | None = None,
) -> MetaSendResult:

    _validate_msisdn(to_msisdn)

    if not template_name:
        raise ValueError("template_name required")

    if not language_code:
        raise ValueError("language_code required")

    logger.info(
        "TRANSPORT_SEND_TEMPLATE_ENTER | to=%s | template=%s | lang=%s | params=%s",
        to_msisdn,
        template_name,
        language_code,
        len(body_params or []),
    )

    try:
        result = _meta_client.send_template(
            to_msisdn=to_msisdn,
            template_name=template_name,
            language_code=language_code,
            body_params=list(body_params or []),
        )

        logger.info(
            "TRANSPORT_SEND_TEMPLATE_SUCCESS | to=%s | template=%s | message_id=%s",
            to_msisdn,
            template_name,
            getattr(result, "message_id", None),
        )

        return result

    except Exception:
        logger.exception(
            "TRANSPORT_SEND_TEMPLATE_FAIL | to=%s | template=%s",
            to_msisdn,
            template_name,
        )
        raise


def send_business_update(
    *,
    to_msisdn: str,
    blob_text: str,
) -> MetaSendResult:

    _validate_msisdn(to_msisdn)

    if not blob_text:
        raise ValueError("blob_text cannot be empty")

    logger.info(
        "TRANSPORT_SEND_BUSINESS_UPDATE_ENTER | to=%s | blob_len=%s",
        to_msisdn,
        len(blob_text),
    )

    try:
        result = _meta_client.send_generic_business_update_template(
            to_msisdn=to_msisdn,
            blob_text=blob_text,
        )

        logger.info(
            "TRANSPORT_SEND_BUSINESS_UPDATE_SUCCESS | to=%s | message_id=%s",
            to_msisdn,
            getattr(result, "message_id", None),
        )

        return result

    except Exception:
        logger.exception(
            "TRANSPORT_SEND_BUSINESS_UPDATE_FAIL | to=%s",
            to_msisdn,
        )
        raise
