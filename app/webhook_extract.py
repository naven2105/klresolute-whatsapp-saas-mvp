from __future__ import annotations

"""
File: app/webhook_extract.py
Path: app/webhook_extract.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Extraction + normalisation layer for inbound provider payloads.

Rules:
- Parse provider payload
- Normalise inbound structure
- Extract phone_number_id, sender, message type, text, media (as present)
- No routing logic
"""

import logging
import re
from typing import Optional


logger = logging.getLogger("webhooks")


def _normalise_msisdn(raw: str | None) -> Optional[str]:
    if not raw:
        logger.warning("MSISDN_NORMALISE_SKIP | reason=empty")
        return None

    digits = re.sub(r"\D", "", raw)

    if digits.startswith("0"):
        digits = "27" + digits[1:]

    if digits.startswith("27") and len(digits) >= 11:
        logger.info("MSISDN_NORMALISED | raw=%s | normalised=%s", raw, digits)
        return digits

    logger.error("MSISDN_NORMALISE_FAIL | raw=%s | digits=%s", raw, digits)
    return None


def extract_message(payload: dict):
    """
    Structural extraction only. Returns the same tuple as the original webhook layer:
    (msg, sender_msisdn, business_msisdn, provider_message_id)
    """
    try:
        logger.info(
            "WEBHOOK_RAW_PAYLOAD_KEYS | keys=%s",
            list(payload.keys()),
        )

        entry = payload["entry"][0]["changes"][0]["value"]

        logger.info(
            "WEBHOOK_VALUE_KEYS | keys=%s",
            list(entry.keys()),
        )

        messages = entry.get("messages")
        statuses = entry.get("statuses")

        if not messages and statuses:
            meta = entry.get("metadata", {})
            status = statuses[0]

            logger.warning(
                "PAYLOAD_STATUS_ONLY | "
                "business_raw=%s | "
                "recipient_id=%s | "
                "status=%s | "
                "status_id=%s | "
                "timestamp=%s | "
                "conversation=%s",
                meta.get("display_phone_number"),
                status.get("recipient_id"),
                status.get("status"),
                status.get("id"),
                status.get("timestamp"),
                status.get("conversation"),
            )

            # ✅ Minimal enhancement: log Meta error details (if provided)
            errors = status.get("errors") or []
            if errors:
                for e in errors:
                    # Keep fields defensive: Meta sometimes varies structure
                    logger.warning(
                        "PAYLOAD_STATUS_ERROR | "
                        "recipient_id=%s | "
                        "status_id=%s | "
                        "code=%s | "
                        "title=%s | "
                        "message=%s | "
                        "details=%s",
                        status.get("recipient_id"),
                        status.get("id"),
                        e.get("code"),
                        e.get("title"),
                        e.get("message"),
                        e.get("error_data") or e.get("details") or e,
                    )

            return None, None, None, None

        if not messages:
            logger.warning(
                "PAYLOAD_NO_MESSAGES | has_statuses=%s",
                bool(statuses),
            )
            return None, None, None, None

        msg = messages[0]
        sender_raw = msg.get("from")
        provider_message_id = msg.get("id")
        business_raw = entry.get("metadata", {}).get("display_phone_number")

        logger.info(
            "MESSAGE_RAW_FIELDS | sender_raw=%s | business_raw=%s | pid=%s | msg_keys=%s",
            sender_raw,
            business_raw,
            provider_message_id,
            list(msg.keys()),
        )

        sender = _normalise_msisdn(sender_raw)
        business = _normalise_msisdn(business_raw)

        logger.info(
            "MESSAGE_EXTRACTED | type=%s | sender=%s | business=%s | pid=%s",
            msg.get("type"),
            sender,
            business,
            provider_message_id,
        )

        return msg, sender, business, provider_message_id

    except Exception:
        logger.exception("PAYLOAD_EXTRACT_FAIL")
        return None, None, None, None