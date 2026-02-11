from __future__ import annotations

"""
File: app/handlers/tier1_admin_entry_galitos.py
Path: app/handlers/tier1_admin_entry_galitos.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Handle Tier-1 Galitos ADMIN flow only.

GUARDS (LOCKED):
- Admin-only entry
- Must NOT handle customer flow
- Must NOT intercept YES / NO
- Admin must ALWAYS receive a response
- MUST NEVER raise exceptions
- MUST fail safe and log clearly (Render-friendly)
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.outbound.factory import get_meta_client
from app.survey import (
    auto_close_expired_surveys,
    get_active_survey,
    record_response,
    build_survey_summary_text,
)

logger = logging.getLogger("handlers.tier1.admin")


ADMIN_MENU_TEXT = (
    "🛠️ Admin Menu\n\n"
    "📊 Surveys\n"
    "⚪ No active survey\n\n"
    "Start surveys (one active at a time):\n\n"
    "SURVEY SENTIMENT: <question>\n"
    "👍 Like   😐 Neutral   👎 Dislike\n\n"
    "SURVEY FREQUENCY: <question>\n"
    "🔁 Often   ➖ Sometimes   ⏳ Rarely\n\n"
    "SURVEY HELPFULNESS: <question>\n"
    "✅ Helpful   😐 Neutral   ❌ Not Helpful\n\n"
    "END SURVEY\n\n"
    "Notes:\n"
    "• Surveys auto-close in 24 hours\n"
    "• Starting a new survey closes the previous one\n"
    "• Survey results are shared with admins when the survey closes\n\n"
    "────────────────\n\n"
    "🎯 Specials\n"
    "SPECIAL: <caption>\n\n"
    "Notes:\n"
    "• Only ONE special at a time\n"
    "• A new special replaces the previous one\n"
    "• Customers can only access the latest special\n"
    "• Send to a single customer only\n\n"
    "────────────────\n\n"
    "⚙️ System\n"
    "STATUS: <message>\n"
    "CLEAR STATUS"
)


# -------------------------------------------------
# Helpers
# -------------------------------------------------

def _send_text(
    *,
    business_msisdn: str,
    to_number: str,
    text_msg: str,
) -> None:
    try:
        meta = get_meta_client(business_msisdn=business_msisdn)
        meta.send_session_message(
            to_msisdn=to_number,
            text=text_msg,
        )
    except Exception:
        logger.exception(
            "ADMIN_SEND_FAIL | business=%s | to=%s",
            business_msisdn,
            to_number,
        )


def _admin_numbers(db: Session, *, business_msisdn: str) -> list[str]:
    try:
        return (
            db.execute(
                text(
                    """
                    SELECT ca.msisdn
                    FROM client_admins ca
                    JOIN whatsapp_numbers w
                      ON UPPER(ca.client_code) = (
                          SELECT UPPER(c.client_name)
                          FROM clients c
                          WHERE c.client_id = w.client_id
                          LIMIT 1
                      )
                    WHERE w.destination_number = :business
                      AND ca.is_active = TRUE
                    """
                ),
                {"business": business_msisdn},
            )
            .scalars()
            .all()
        )
    except Exception:
        logger.exception(
            "ADMIN_LOOKUP_FAIL | business=%s",
            business_msisdn,
        )
        return []


# -------------------------------------------------
# Public entry
# -------------------------------------------------

def handle_admin_entry(
    *,
    db: Session,
    sender_number: str,
    message_text: str,
    msg: dict | None,
    business_msisdn: str | None,
) -> bool:
    """
    Returns True if handled.

    GUARANTEE:
    - Admin must ALWAYS receive a response.
    - Never raises; never breaks caller.
    """
    try:
        if not business_msisdn:
            logger.error(
                "ADMIN_BLOCKED | reason=missing_business_msisdn | sender=%s",
                sender_number,
            )
            return True

        upper = (message_text or "").strip().upper()

        # ----------------------------------
        # Survey auto-close (safe)
        # ----------------------------------
        try:
            closed = auto_close_expired_surveys(db, business_msisdn)
            if closed:
                summary = build_survey_summary_text(db, closed)
                for admin in _admin_numbers(db, business_msisdn=business_msisdn):
                    _send_text(
                        business_msisdn=business_msisdn,
                        to_number=admin,
                        text_msg=summary,
                    )
        except Exception:
            logger.exception(
                "ADMIN_SURVEY_AUTOCLOSE_FAIL | business=%s",
                business_msisdn,
            )

        # ----------------------------------
        # Survey button replies
        # ----------------------------------
        if msg and msg.get("type") == "interactive":
            try:
                button_id = (
                    msg.get("interactive", {})
                    .get("button_reply", {})
                    .get("id")
                )
                if button_id:
                    active = get_active_survey(db, business_msisdn)
                    if active and record_response(
                        db=db,
                        survey=active,
                        client_number=sender_number,
                        button_id=button_id,
                    ):
                        _send_text(
                            business_msisdn=business_msisdn,
                            to_number=sender_number,
                            text_msg="Thank you for your response.",
                        )
                return True
            except Exception:
                logger.exception(
                    "ADMIN_SURVEY_RESPONSE_FAIL | sender=%s",
                    sender_number,
                )
                return True

        # ----------------------------------
        # Admin menu (explicit)
        # ----------------------------------
        if upper == "MENU":
            _send_text(
                business_msisdn=business_msisdn,
                to_number=sender_number,
                text_msg=ADMIN_MENU_TEXT,
            )
            return True

        # ----------------------------------
        # GUARANTEED RESPONSE (fallback)
        # ----------------------------------
        logger.info(
            "ADMIN_NO_MATCH | sender=%s | text=%r | action=send_menu",
            sender_number,
            message_text,
        )
        _send_text(
            business_msisdn=business_msisdn,
            to_number=sender_number,
            text_msg=ADMIN_MENU_TEXT,
        )
        return True

    except Exception:
        logger.exception(
            "ADMIN_ENTRY_FATAL | sender=%s",
            sender_number,
        )
        return True
