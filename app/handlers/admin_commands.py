from __future__ import annotations

"""
File: app/handlers/admin_commands.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Admin command router (Tier-1).

Responsibilities:
- Idempotency / duplicate protection
- Routing to admin_* handlers
- Defensive error handling
- Logging ONLY (no business logic)

LOCKED:
- No survey logic
- No messaging logic
"""

import logging
import time
import hashlib
from sqlalchemy.orm import Session

from app.clients.galitos.handlers.admin_surveys import handle_admin_surveys
from app.handlers.admin_messaging import handle_admin_messaging
from app.utils.admin import is_admin_message

logger = logging.getLogger("admin_commands")

# ------------------------------------------------------------------
# Idempotency (in-memory, short-lived)
# ------------------------------------------------------------------

_IDEMPOTENCY_CACHE: dict[str, float] = {}
_IDEMPOTENCY_TTL_SECONDS = 30


def _build_idempotency_key(
    *,
    sender_number: str,
    message_text: str,
) -> str:
    """
    Stable hash so Meta retries are ignored.
    """
    raw = f"{sender_number}|{message_text.strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _is_duplicate(key: str) -> bool:
    now = time.time()

    # purge expired keys
    expired = [
        k for k, ts in _IDEMPOTENCY_CACHE.items()
        if now - ts > _IDEMPOTENCY_TTL_SECONDS
    ]
    for k in expired:
        del _IDEMPOTENCY_CACHE[k]

    if key in _IDEMPOTENCY_CACHE:
        return True

    _IDEMPOTENCY_CACHE[key] = now
    return False


# ------------------------------------------------------------------
# Router
# ------------------------------------------------------------------

def handle_admin_command(
    *,
    db: Session,
    sender_number: str,
    message_text: str,
    business_msisdn: str,
) -> bool:
    """
    Entry point for ALL admin commands.
    """

    logger.info(
        "ADMIN_ROUTER_ENTER | sender=%s | raw=%r",
        sender_number,
        message_text,
    )

    # --------------------------------------------------------------
    # Admin check (DB-driven, FAIL CLOSED)
    # --------------------------------------------------------------
    if not is_admin_message(
        db=db,
        sender=sender_number,
        business_msisdn=business_msisdn,
    ):
        logger.info(
            "ADMIN_ROUTER_REJECT | not admin | sender=%s",
            sender_number,
        )
        return False

    clean_text = (message_text or "").strip()
    if not clean_text:
        logger.info("ADMIN_ROUTER_EMPTY_TEXT")
        return True

    # --------------------------------------------------------------
    # Idempotency guard
    # --------------------------------------------------------------
    idem_key = _build_idempotency_key(
        sender_number=sender_number,
        message_text=clean_text,
    )

    if _is_duplicate(idem_key):
        logger.warning(
            "ADMIN_ROUTER_DUPLICATE_IGNORED | sender=%s | key=%s",
            sender_number,
            idem_key[:12],
        )
        return True

    # --------------------------------------------------------------
    # Dispatch order (STRICT)
    # --------------------------------------------------------------

    try:
        if handle_admin_surveys(
            db=db,
            sender_number=sender_number,
            message_text=clean_text,
            business_msisdn=business_msisdn,
        ):
            logger.info("ADMIN_ROUTER_HANDLED | handler=surveys")
            return True
    except Exception as exc:
        logger.error(
            "ADMIN_ROUTER_SURVEYS_FAIL | error=%s",
            exc,
            exc_info=True,
        )
        return True

    try:
        if handle_admin_messaging(
            db=db,
            sender_number=sender_number,
            message_text=clean_text,
            business_msisdn=business_msisdn,
        ):
            logger.info("ADMIN_ROUTER_HANDLED | handler=messaging")
            return True
    except Exception as exc:
        logger.error(
            "ADMIN_ROUTER_MESSAGING_FAIL | error=%s",
            exc,
            exc_info=True,
        )
        return True

    logger.warning(
        "ADMIN_ROUTER_FALLTHROUGH | sender=%s | text=%r",
        sender_number,
        clean_text,
    )
    return True
