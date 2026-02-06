from __future__ import annotations

"""
File: app/handlers/tier1_admin_handler.py
Path: app/handlers/tier1_admin_handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Admin-specific Tier-1 handling.

Rules (LOCKED):
- Admins only
- No customer menu logic
- No order handling
- Fail closed
"""

import logging
from sqlalchemy.orm import Session

from app.outbound.factory import get_meta_client
from app.utils.admin import is_admin_message

from app.survey import (
    auto_close_expired_surveys,
    get_active_survey,
    record_response,
    build_survey_summary_text,
)

logger = logging.getLogger("handlers.tier1_admin")

ADMIN_MENU_TEXT = (
    "🛠️ Admin Menu\n\n"
    "📊 Surveys\n"
    "SURVEY SENTIMENT: <question>\n"
    "SURVEY FREQUENCY: <question>\n"
    "SURVEY HELPFULNESS: <question>\n"
    "END SURVEY\n\n"
    "✉️ Messaging\n"
    "SEND: <number> <message>\n"
    "BROADCAST: <message>\n\n"
    "⚙️ System\n"
    "PAUSE\n"
    "RESUME"
)


def handle_admin_command(
    *,
    db: Session,
    sender_number: str,
    message_text: str,
    msg: dict | None,
    business_msisdn: str | None,
) -> bool:
    """
    Returns True if admin message was handled.
    """

    if not business_msisdn:
        logger.error(
            "ADMIN_HANDLER_BLOCKED | reason=missing_business_number | sender=%s",
            sender_number,
        )
        return False

    if not is_admin_message(
        db=db,
        sender=sender_number,
        business_msisdn=business_msisdn,
    ):
        return False

    meta = get_meta_client(business_msisdn=business_msisdn)
    upper = (message_text or "").strip().upper()

    logger.info(
        "ADMIN_CMD_ENTER | sender=%s | text=%s | business=%s",
        sender_number,
        upper,
        business_msisdn,
    )

    # -------------------------------------------------
    # Survey auto-close (safe)
    # -------------------------------------------------
    try:
        closed = auto_close_expired_surveys(db, business_msisdn)
        if closed:
            summary = build_survey_summary_text(db, closed)
            meta.send_session_message(
                to_msisdn=sender_number,
                text=summary,
            )
    except Exception:
        logger.exception(
            "ADMIN_SURVEY_AUTO_CLOSE_FAIL | sender=%s",
            sender_number,
        )

    # -------------------------------------------------
    # Survey button replies
    # -------------------------------------------------
    if msg and msg.get("type") == "interactive":
        try:
            button_reply = (
                msg.get("interactive", {})
                .get("button_reply", {})
                .get("id")
            )
            if button_reply:
                active = get_active_survey(db, business_msisdn)
                if active and record_response(
                    db=db,
                    survey=active,
                    client_number=sender_number,
                    button_id=button_reply,
                ):
                    meta.send_session_message(
                        to_msisdn=sender_number,
                        text="Thank you for your response.",
                    )
                return True
        except Exception:
            logger.exception(
                "ADMIN_SURVEY_RESPONSE_FAIL | sender=%s",
                sender_number,
            )
            return True

    # -------------------------------------------------
    # Admin MENU
    # -------------------------------------------------
    if upper == "MENU":
        meta.send_session_message(
            to_msisdn=sender_number,
            text=ADMIN_MENU_TEXT,
        )
        return True

    # -------------------------------------------------
    # Admin fallback (important)
    # -------------------------------------------------
    logger.info(
        "ADMIN_FALLBACK_MENU | sender=%s | text=%s",
        sender_number,
        upper,
    )

    meta.send_session_message(
        to_msisdn=sender_number,
        text=ADMIN_MENU_TEXT,
    )
    return True
