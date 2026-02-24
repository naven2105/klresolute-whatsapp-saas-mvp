from __future__ import annotations

"""
File: app/webhook_guards.py
Path: app/webhook_guards.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Inbound validation gates / enforcement rules.

Rules:
- Staff enforcement rules
- Magen enforcement rules
- Any inbound validation gates
- Reject unauthorised flows
- No routing logic
"""

import logging

from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.messaging.client_messenger import send_message


logger = logging.getLogger("webhooks")

# -------------------------------------------------
# 🔒 Magen Internal Enforcement Constants
# -------------------------------------------------
MAGEN_BUSINESS_NUMBER = "27631016099"
MAGEN_INTERNAL_ONLY_MESSAGE = "This bot is for Magen internal use only."

# Galitos business number (for scoped staff guard)
GALITOS_BUSINESS_NUMBER = "27735534607"


def guard_db_available_or_notify(
    *,
    db: Session,
    sender: str,
    business_msisdn: str,
) -> bool:
    try:
        db.execute(text("SELECT 1"))
        logger.info("DB_OK")
        return True
    except OperationalError:
        logger.critical("DB_UNAVAILABLE | sender=%s", sender)
        send_message(
            db=db,
            business_msisdn=business_msisdn,
            to_number=sender,
            text="⚠️ Service temporarily unavailable. Please try again shortly.",
        )
        return False


def _is_active_magen_staff(db: Session, *, sender_msisdn: str) -> bool:
    try:
        row = (
            db.execute(
                text(
                    """
                    SELECT 1
                    FROM magen_staff
                    WHERE msisdn = :msisdn
                      AND is_active = true
                    LIMIT 1
                    """
                ),
                {"msisdn": sender_msisdn},
            )
            .first()
        )

        is_staff = bool(row)

        logger.info(
            "MAGEN_STAFF_CHECK | sender=%s | is_active=%s",
            sender_msisdn,
            is_staff,
        )

        return is_staff

    except Exception:
        logger.exception(
            "MAGEN_STAFF_CHECK_FAIL | sender=%s",
            sender_msisdn,
        )
        return False


def guard_magen_internal_only(
    *,
    db: Session,
    sender: str,
    business_msisdn: str,
) -> bool:
    if business_msisdn != MAGEN_BUSINESS_NUMBER:
        return True

    if _is_active_magen_staff(db, sender_msisdn=sender):
        return True

    logger.warning(
        "MAGEN_UNAUTHORISED_ATTEMPT | sender=%s | business=%s",
        sender,
        business_msisdn,
    )
    try:
        send_message(
            db=db,
            business_msisdn=business_msisdn,
            to_number=sender,
            text=MAGEN_INTERNAL_ONLY_MESSAGE,
        )
    except Exception:
        logger.exception(
            "MAGEN_UNAUTHORISED_SEND_FAIL | sender=%s",
            sender,
        )
    return False


def _is_active_galitos_staff(db: Session, *, sender_msisdn: str) -> bool:
    try:
        row = (
            db.execute(
                text(
                    """
                    SELECT 1
                    FROM galitos_staff
                    WHERE msisdn = :msisdn
                      AND is_active = true
                    LIMIT 1
                    """
                ),
                {"msisdn": sender_msisdn},
            )
            .first()
        )

        is_staff = bool(row)
        logger.info(
            "STAFF_INBOUND_CHECK | sender=%s | is_active_staff=%s",
            sender_msisdn,
            is_staff,
        )
        return is_staff

    except Exception:
        logger.exception("STAFF_INBOUND_CHECK_FAIL | sender=%s", sender_msisdn)
        return False


def guard_scoped_galitos_staff_block(
    *,
    db: Session,
    sender: str,
    business_msisdn: str,
) -> bool:
    if business_msisdn != GALITOS_BUSINESS_NUMBER:
        return True

    if not _is_active_galitos_staff(db, sender_msisdn=sender):
        return True

    logger.warning(
        "WEBHOOK_ABORT | reason=staff_inbound_blocked | sender=%s | business=%s",
        sender,
        business_msisdn,
    )
    return False