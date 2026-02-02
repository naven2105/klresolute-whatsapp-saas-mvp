from __future__ import annotations

"""
File: app/handlers/tier1_router.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Tier 1 Router (Client + Admin entry point)

GUARD RAILS (LOCKED):
- MUST NOT handle order flow
- MUST NOT intercept YES / NO
- MUST NOT require profile DB for orders
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.outbound.meta import MetaWhatsAppClient
from app.outbound.settings import load_meta_settings
from app.utils.admin import is_admin_message

from app.survey import (
    auto_close_expired_surveys,
    get_active_survey,
    record_response,
    build_survey_summary_text,
)

from app.clients.galitos.customer_commands import (
    handle_client_command as handle_customer_commands
)

logger = logging.getLogger("handlers.tier1_router")

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

_meta_client = MetaWhatsAppClient(settings=load_meta_settings())


# =================================================
# Helpers
# =================================================

def _send_text(to_number: str, text_msg: str) -> None:
    logger.info("SEND_TEXT | to=%s | text=%r", to_number, text_msg)
    _meta_client.send_session_message(to_msisdn=to_number, text=text_msg)


def _get_client_message(
    db: Session,
    *,
    business_number: str,
    message_key: str,
) -> str | None:
    try:
        row = (
            db.execute(
                text(
                    """
                    SELECT cm.message_text
                    FROM client_messages cm
                    JOIN whatsapp_numbers w ON w.client_id = cm.client_id
                    WHERE w.destination_number = :business
                      AND cm.message_key = :key
                      AND cm.is_active = TRUE
                    LIMIT 1
                    """
                ),
                {"business": business_number, "key": message_key},
            )
            .mappings()
            .first()
        )
        return row["message_text"] if row else None
    except Exception as exc:
        logger.exception(
            "CLIENT_MESSAGE_FETCH_FAIL | business=%s | key=%s | err=%s",
            business_number,
            message_key,
            exc,
        )
        return None


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
    except Exception as exc:
        logger.exception("ADMIN_LOOKUP_FAIL | err=%s", exc)
        return []


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

        # -------------------------------------------------
        # HARD ORDER GUARD — NEVER TOUCH ORDER CONFIRMATION
        # -------------------------------------------------
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

        # -------------------------------------------------
        # Survey auto-close (safe)
        # -------------------------------------------------
        if business_number:
            try:
                closed = auto_close_expired_surveys(db, business_number)
                if closed:
                    summary = build_survey_summary_text(db, closed)
                    for admin in _admin_numbers(db):
                        _send_text(admin, summary)
            except Exception as exc:
                logger.exception(
                    "SURVEY_AUTO_CLOSE_FAIL | business=%s | err=%s",
                    business_number,
                    exc,
                )

        # -------------------------------------------------
        # Survey button replies
        # -------------------------------------------------
        if msg and msg.get("type") == "interactive" and business_number:
            try:
                button_reply = (
                    msg.get("interactive", {})
                    .get("button_reply", {})
                    .get("id")
                )
                if button_reply:
                    active = get_active_survey(db, business_number)
                    if active and record_response(
                        db=db,
                        survey=active,
                        client_number=sender_number,
                        button_id=button_reply,
                    ):
                        _send_text(sender_number, "Thank you for your response.")
                return True
            except Exception as exc:
                logger.exception(
                    "SURVEY_RESPONSE_FAIL | sender=%s | err=%s",
                    sender_number,
                    exc,
                )
                return True

        # -------------------------------------------------
        # Admin menu
        # -------------------------------------------------
        if is_admin and upper == "MENU":
            _send_text(sender_number, ADMIN_MENU_TEXT)
            return True

        # -------------------------------------------------
        # ABOUT / HOURS
        # -------------------------------------------------
        if not is_admin and business_number and upper in ("ABOUT", "HOURS"):
            msg_text = _get_client_message(
                db,
                business_number=business_number,
                message_key=upper.lower(),
            )
            if msg_text:
                _send_text(sender_number, msg_text)
            return True

        # -------------------------------------------------
        # FEEDBACK
        # -------------------------------------------------
        if not is_admin and upper.startswith("FEEDBACK"):
            if ":" in message_text:
                feedback = message_text.split(":", 1)[1].strip()
                if feedback:
                    _send_text(
                        sender_number,
                        "Thank you — we’ve received your feedback.",
                    )
                    for admin in _admin_numbers(db):
                        _send_text(
                            admin,
                            f"📝 Feedback\nFrom: {sender_number}\n\n{feedback}",
                        )
            return True

        # -------------------------------------------------
        # Delegate non-order customer commands
        # -------------------------------------------------
        if not is_admin:
            return bool(
                handle_customer_commands(
                    db=db,
                    sender=sender_number,
                    msg=msg or {"type": "text", "text": {"body": message_text or ""}},
                    client_id=str(resolved_client_id) if resolved_client_id else "",
                    business_msisdn=business_number,
                )
            )

        return False

    except Exception as exc:
        logger.exception(
            "TIER1_ROUTER_FATAL | sender=%s | err=%s",
            sender_number,
            exc,
        )
        return True
