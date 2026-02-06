from __future__ import annotations

"""
File: app/handlers/tier1_router.py
Path: app/handlers/tier1_router.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Tier 1 Router (Client + Admin entry point)

GUARD RAILS (LOCKED):
- MUST NOT handle order flow
- MUST NOT intercept YES / NO
- MUST NOT require profile DB for orders

DB TRUTH (VERIFIED):
- client_contacts.client_id is INTEGER (MVP reality)
- Tier-1 must NOT attempt UUID client_id resolution.
- Tier-1 must only use the upstream resolved integer client_id.
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.outbound.factory import get_meta_client
from app.utils.admin import is_admin_message
from app.modules.status.reader import get_active_status

from app.survey import (
    auto_close_expired_surveys,
    get_active_survey,
    record_response,
    build_survey_summary_text,
)

from app.clients.galitos.customer_commands import (
    handle_client_command as handle_customer_commands,
)

logger = logging.getLogger("handlers.tier1_router")

ADMIN_MENU_TEXT = (
    "🛠️ Admin Menu\n\n"
    "📊 Surveys\n"
    "SURVEY SENTIMENT: <question>\n"
    "SURVEY FREQUENCY: <question>\n"
    "SURVEY HELPFULNESS: <question>\n"
    "END SURVEY\n\n"
    "⚙️ System\n"
    "STATUS: <message>\n"
    "CLEAR STATUS"
)


# =================================================
# Helpers
# =================================================

def _send_text(*, business_number: str | None, to_number: str, text_msg: str) -> None:
    if not business_number:
        logger.error(
            "TIER1_SEND_BLOCKED | reason=missing_business_number | to=%s | text=%r",
            to_number,
            text_msg,
        )
        return

    meta = get_meta_client(business_msisdn=business_number)
    meta.send_session_message(to_msisdn=to_number, text=text_msg)


def _admin_numbers(db: Session) -> list[str]:
    try:
        return (
            db.execute(
                text(
                    """
                    SELECT msisdn
                    FROM client_admins
                    WHERE is_active = TRUE
                    """
                )
            )
            .scalars()
            .all()
        )
    except Exception:
        logger.exception("ADMIN_LOOKUP_FAIL")
        return []


def _ensure_client_contact(
    db: Session,
    *,
    client_id: int,
    contact_number: str,
) -> None:
    try:
        row = (
            db.execute(
                text(
                    """
                    SELECT 1
                    FROM client_contacts
                    WHERE client_id = :client_id
                      AND contact_number = :contact
                    LIMIT 1
                    """
                ),
                {"client_id": client_id, "contact": contact_number},
            )
            .first()
        )

        if row:
            return

        db.execute(
            text(
                """
                INSERT INTO client_contacts (client_id, contact_number, is_opted_out, created_at)
                VALUES (:client_id, :contact, FALSE, now())
                """
            ),
            {"client_id": client_id, "contact": contact_number},
        )
        db.commit()

    except Exception:
        db.rollback()
        logger.exception(
            "SILENT_JOIN_FAIL | client_id=%s | contact=%s",
            client_id,
            contact_number,
        )


def _parse_resolved_client_id_int(resolved_client_id: str | None) -> int | None:
    if not resolved_client_id:
        return None
    try:
        return int(str(resolved_client_id))
    except Exception:
        logger.exception(
            "CLIENT_ID_PARSE_FAIL | resolved_client_id=%r",
            resolved_client_id,
        )
        return None


# =================================================
# Main handler
# =================================================

def handle_client_command(
    *,
    db: Session,
    sender_number: str,
    message_text: str,
    msg: dict | None = None,
    resolved_client_id: str | None = None,
    resolved_business_number: str | None = None,
    resolved_phone_number_id: str | None = None,
) -> bool:
    try:
        business_number = resolved_business_number
        upper = (message_text or "").strip().upper()

        # ----------------------------------
        # HARD ORDER GUARD
        # ----------------------------------
        if upper in ("YES", "NO"):
            logger.info(
                "ORDER_CONFIRMATION_BYPASS_TIER1 | sender=%s",
                sender_number,
            )
            return False

        is_admin = (
            business_number
            and is_admin_message(
                db=db,
                sender=sender_number,
                business_msisdn=business_number,
            )
        )

        # ----------------------------------
        # Survey auto-close (safe)
        # ----------------------------------
        if business_number:
            try:
                closed = auto_close_expired_surveys(db, business_number)
                if closed:
                    summary = build_survey_summary_text(db, closed)
                    for admin in _admin_numbers(db):
                        _send_text(
                            business_number=business_number,
                            to_number=admin,
                            text_msg=summary,
                        )
            except Exception:
                logger.exception("SURVEY_AUTO_CLOSE_FAIL")

        # ----------------------------------
        # Explicit admin MENU command
        # ----------------------------------
        if is_admin and upper == "MENU":
            logger.info(
                "ADMIN_MENU_REQUEST | sender=%s",
                sender_number,
            )
            _send_text(
                business_number=business_number,
                to_number=sender_number,
                text_msg=ADMIN_MENU_TEXT,
            )
            return True

        # ----------------------------------
        # ✅ ADMIN FALLBACK (MANDATORY)
        # ----------------------------------
        if is_admin:
            logger.info(
                "ADMIN_FALLBACK_MENU | sender=%s | text=%r",
                sender_number,
                message_text,
            )
            _send_text(
                business_number=business_number,
                to_number=sender_number,
                text_msg=ADMIN_MENU_TEXT,
            )
            return True

        # ----------------------------------
        # CUSTOMER PATH
        # ----------------------------------
        client_id_int = _parse_resolved_client_id_int(resolved_client_id)
        if client_id_int is None:
            logger.error(
                "CLIENT_RESOLUTION_FAILED | sender=%s | resolved_client_id=%r",
                sender_number,
                resolved_client_id,
            )
            return True

        _ensure_client_contact(
            db,
            client_id=client_id_int,
            contact_number=sender_number,
        )

        # ----------------------------------
        # STATUS READ (before customer menu)
        # ----------------------------------
        status_text = (
            get_active_status(
                db=db,
                business_msisdn=business_number,
            )
            if business_number
            else None
        )

        if status_text:
            _send_text(
                business_number=business_number,
                to_number=sender_number,
                text_msg=f"⚠️ NOTICE\n\n{status_text}\n\n———",
            )

        return bool(
            handle_customer_commands(
                db=db,
                sender=sender_number,
                msg=msg or {"type": "text", "text": {"body": message_text or ""}},
                client_id=str(client_id_int),
                business_msisdn=business_number or "",
            )
        )

    except Exception:
        logger.exception(
            "TIER1_ROUTER_FATAL | sender=%s",
            sender_number,
        )
        return True
