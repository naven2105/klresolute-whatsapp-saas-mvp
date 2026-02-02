from __future__ import annotations

"""
File: app/handlers/tier1_router.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Tier 1 Router (Client + Admin entry point)

Responsibilities:
- Resolve business context (client_id + business_number)
- Admin gating (admin never sees customer menu)
- Survey auto-close + survey button replies
- Guarded JOIN / STOP
- Stateless customer features (ABOUT/HOURS, SPECIALS, FEEDBACK)
- Delegate remaining customer text to client-specific handler(s)

Guardrails (LOCKED INTENT):
- Do NOT touch order flow logic here (orders are handled elsewhere and frozen)
- No dispatcher reordering required for this module to work
"""

import logging
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.outbound.meta import MetaWhatsAppClient
from app.outbound.settings import load_meta_settings
from app.services.contacts_service import add_contact, remove_contact
from app.models import WhatsAppNumber, Contact
from app.utils.admin import is_admin_message

# =========================
# Survey imports
# =========================
from app.survey import (
    auto_close_expired_surveys,
    get_active_survey,
    record_response,
    build_survey_summary_text,
)
from app.survey.survey_constants import CUSTOMER_SURVEY_THANK_YOU_TEMPLATE

# =========================
# Delegate customer handler (Galitos)
# =========================
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
    "✉️ Messaging\n"
    "SEND: <number> <message>\n"
    "BROADCAST: <message>\n\n"
    "⚙️ System\n"
    "PAUSE\n"
    "RESUME"
)

_meta_client = MetaWhatsAppClient(settings=load_meta_settings())


# =========================
# Helpers
# =========================
def _send_text(to_number: str, text_msg: str) -> None:
    logger.info("SEND_TEXT | to=%s | text=%r", to_number, text_msg)
    _meta_client.send_session_message(to_msisdn=to_number, text=text_msg)


def _get_client_message(
    db: Session,
    *,
    business_number: str,
    message_key: str,
) -> str | None:
    """
    Fetches a DB-driven client message by key for the resolved business number.
    Returns None when missing (and logs at INFO so missing config is visible).
    """
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
        if not row:
            logger.info(
                "CLIENT_MESSAGE_MISSING | business=%s | key=%s",
                business_number,
                message_key,
            )
            return None
        return row["message_text"]

    except Exception as exc:
        logger.exception(
            "CLIENT_MESSAGE_FETCH_FAIL | business=%s | key=%s | err=%s",
            business_number,
            message_key,
            exc,
        )
        return None


def _send_latest_special(db: Session, to_number: str, client_id: Any) -> None:
    """
    Sends the latest special for the client.
    Guard rail: attempts an 'is_active' filter first; if the column doesn't exist
    in older schemas, falls back to the legacy query.
    """
    if not client_id:
        logger.warning("SPECIALS_NO_CLIENT_ID | to=%s", to_number)
        _send_text(to_number, "No specials are available right now.")
        return

    # Attempt 1: schema with is_active
    try:
        row = (
            db.execute(
                text(
                    """
                    SELECT media_id, caption
                    FROM specials
                    WHERE client_id = :client_id
                      AND is_active = TRUE
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                ),
                {"client_id": client_id},
            )
            .mappings()
            .first()
        )

        if not row:
            _send_text(to_number, "No specials are available right now.")
            return

        _meta_client.send_image_message(
            to_msisdn=to_number,
            media_id=row["media_id"],
            caption=row["caption"],
        )
        return

    except Exception as exc:
        logger.warning(
            "SPECIALS_QUERY_IS_ACTIVE_FAIL | client_id=%s | err=%s | falling_back=legacy",
            client_id,
            exc,
        )

    # Attempt 2: legacy schema (no is_active column)
    try:
        row = (
            db.execute(
                text(
                    """
                    SELECT media_id, caption
                    FROM specials
                    WHERE client_id = :client_id
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                ),
                {"client_id": client_id},
            )
            .mappings()
            .first()
        )

        if not row:
            _send_text(to_number, "No specials are available right now.")
            return

        _meta_client.send_image_message(
            to_msisdn=to_number,
            media_id=row["media_id"],
            caption=row["caption"],
        )

    except Exception as exc:
        logger.exception(
            "SEND_SPECIAL_FAIL | to=%s | client_id=%s | err=%s",
            to_number,
            client_id,
            exc,
        )
        _send_text(to_number, "No specials are available right now.")


def _resolve_store_context_fallback(db: Session) -> tuple[Any | None, str | None]:
    """
    Last-resort resolver when dispatcher didn't provide resolved_client_id / business number.
    Guard rail: logs loudly; this should not be the normal path.
    """
    try:
        wa = (
            db.query(WhatsAppNumber)
            .filter(WhatsAppNumber.status == "active")
            .first()
        )
        if not wa:
            logger.error("NO_ACTIVE_WHATSAPP_NUMBER | fallback_store_context")
            return None, None

        logger.warning(
            "FALLBACK_CONTEXT_USED | client_id=%s | business=%s",
            wa.client_id,
            wa.destination_number,
        )
        return wa.client_id, wa.destination_number

    except Exception as exc:
        logger.exception("STORE_CONTEXT_RESOLVE_FAIL | err=%s", exc)
        return None, None


def _admin_numbers_for_business(db: Session, business_number: str | None) -> list[str]:
    """
    Fetch admin numbers. Current schema in use appears to be 'client_admins' with is_active.
    Guard rail: if business context is missing or query fails, returns empty list.
    """
    if not business_number:
        return []

    try:
        # NOTE: Keeping your existing behaviour (no extra filters) to avoid schema breakage.
        # If/when client_admins is scoped by client/business, we will tighten this filter.
        admins = (
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
        return [a for a in admins if a]

    except Exception as exc:
        logger.exception(
            "ADMIN_LOOKUP_FAIL | business=%s | err=%s",
            business_number,
            exc,
        )
        return []


def _handle_feedback(
    *,
    db: Session,
    sender_number: str,
    business_number: str | None,
    message_text: str,
) -> bool:
    """
    Stateless FEEDBACK:
    - Customer gets short acknowledgement
    - Admin receives feedback immediately
    - No state created
    """
    raw = (message_text or "").strip()
    if not raw:
        return False

    upper = raw.upper()
    if not upper.startswith("FEEDBACK"):
        return False

    # Accept "FEEDBACK: ..." only (as per requirement)
    if ":" not in raw:
        _send_text(sender_number, "Please send: FEEDBACK: <your message>")
        logger.info("FEEDBACK_BAD_FORMAT | sender=%s", sender_number)
        return True

    feedback_text = raw.split(":", 1)[1].strip()
    if not feedback_text:
        _send_text(sender_number, "Please send: FEEDBACK: <your message>")
        logger.info("FEEDBACK_EMPTY | sender=%s", sender_number)
        return True

    _send_text(sender_number, "Thank you — we’ve received your feedback.")

    admins = _admin_numbers_for_business(db, business_number)
    if not admins:
        logger.warning(
            "FEEDBACK_NO_ADMINS | business=%s | sender=%s",
            business_number,
            sender_number,
        )
        return True

    admin_msg = (
        "📝 Galitos Feedback\n\n"
        f"From: {sender_number}\n"
        f"Business: {business_number or 'unknown'}\n\n"
        f"{feedback_text}"
    )
    for admin in admins:
        _send_text(admin, admin_msg)

    logger.info(
        "FEEDBACK_FORWARDED | sender=%s | business=%s | admins=%d",
        sender_number,
        business_number,
        len(admins),
    )
    return True


# =========================
# Main handler
# =========================
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
    """
    Tier-1 entry point. Returns True if handled.
    """
    try:
        client_id = resolved_client_id
        business_number = resolved_business_number

        if not client_id or not business_number:
            client_id, business_number = _resolve_store_context_fallback(db)

        if not business_number:
            logger.error(
                "NO_BUSINESS_CONTEXT | sender=%s | resolved_client_id=%s | resolved_business=%s",
                sender_number,
                resolved_client_id,
                resolved_business_number,
            )

        is_admin = (
            bool(business_number)
            and is_admin_message(
                db=db,
                sender=sender_number,
                business_msisdn=business_number,
            )
        )

        # ----------------------------------
        # Auto-close surveys
        # ----------------------------------
        if business_number:
            try:
                closed = auto_close_expired_surveys(db, business_number)
                if closed:
                    summary = build_survey_summary_text(db, closed)
                    admins = _admin_numbers_for_business(db, business_number)
                    for admin in admins:
                        _send_text(admin, summary)

            except Exception as exc:
                logger.exception(
                    "SURVEY_AUTO_CLOSE_FAIL | business=%s | err=%s",
                    business_number,
                    exc,
                )

        # ----------------------------------
        # Survey button replies
        # ----------------------------------
        if msg and msg.get("type") == "interactive" and business_number:
            try:
                button_reply = (
                    msg.get("interactive", {})
                    .get("button_reply", {})
                    .get("id")
                )

                if button_reply:
                    active = get_active_survey(db, business_number)
                    if active:
                        ok = record_response(
                            db=db,
                            survey=active,
                            client_number=sender_number,
                            button_id=button_reply,
                        )
                        if ok:
                            _send_text(
                                sender_number,
                                CUSTOMER_SURVEY_THANK_YOU_TEMPLATE,
                            )
                return True

            except Exception as exc:
                logger.exception(
                    "SURVEY_RESPONSE_FAIL | sender=%s | err=%s",
                    sender_number,
                    exc,
                )
                return True

        # ----------------------------------
        # Text commands
        # ----------------------------------
        raw_text = (message_text or "").strip()
        upper = raw_text.upper()

        # Admin MENU only
        if is_admin and upper == "MENU":
            _send_text(sender_number, ADMIN_MENU_TEXT)
            return True

        # ----------------------------------
        # FEEDBACK (customer only)
        # ----------------------------------
        if not is_admin:
            if _handle_feedback(
                db=db,
                sender_number=sender_number,
                business_number=business_number,
                message_text=raw_text,
            ):
                return True

        # ----------------------------------
        # JOIN (DB-DRIVEN, GUARDED) - customer only
        # ----------------------------------
        if upper == "JOIN" and not is_admin:
            try:
                existing = (
                    db.query(Contact)
                    .filter(Contact.contact_number == sender_number)
                    .one_or_none()
                )

                if existing:
                    msg_text = (
                        _get_client_message(
                            db,
                            business_number=business_number or "",
                            message_key="join_exists",
                        )
                        if business_number
                        else None
                    )
                    if msg_text:
                        _send_text(sender_number, msg_text)
                    return True

                add_contact(db, msisdn=sender_number)

                msg_text = (
                    _get_client_message(
                        db,
                        business_number=business_number or "",
                        message_key="join_success",
                    )
                    if business_number
                    else None
                )
                if msg_text:
                    _send_text(sender_number, msg_text)
                return True

            except Exception as exc:
                logger.exception(
                    "JOIN_FAIL | sender=%s | err=%s",
                    sender_number,
                    exc,
                )
                return True

        # STOP (customer only)
        if upper == "STOP" and not is_admin:
            try:
                remove_contact(db, msisdn=sender_number)
                return True
            except Exception as exc:
                logger.exception("STOP_FAIL | sender=%s | err=%s", sender_number, exc)
                return True

        # ----------------------------------
        # ABOUT / HOURS (DB-driven, customer only)
        # ----------------------------------
        if not is_admin and business_number and upper in ("ABOUT", "HOURS"):
            key = "about" if upper == "ABOUT" else "hours"
            msg_text = _get_client_message(
                db,
                business_number=business_number,
                message_key=key,
            )

            if not msg_text:
                # Guard rail: no hardcoded business content; only a neutral message.
                _send_text(sender_number, "This information is not available right now.")
                logger.warning(
                    "ABOUT_HOURS_MISSING | business=%s | key=%s",
                    business_number,
                    key,
                )
                return True

            _send_text(sender_number, msg_text)
            return True

        # ----------------------------------
        # SPECIALS (customer only)
        # ----------------------------------
        if not is_admin and upper in ("SPECIAL", "SPECIALS"):
            _send_latest_special(db, sender_number, client_id)
            return True

        # ----------------------------------
        # Delegate customer text (Galitos)
        # ----------------------------------
        if not is_admin:
            handled = handle_customer_commands(
                db=db,
                sender=sender_number,
                msg=msg or {"type": "text", "text": {"body": message_text or ""}},
                client_id=str(client_id) if client_id else "",
                business_msisdn=business_number,
            )
            logger.info(
                "DELEGATE_CUSTOMER | handled=%s | sender=%s | business=%s",
                bool(handled),
                sender_number,
                business_number,
            )
            return bool(handled)

        return False

    except Exception as exc:
        logger.exception(
            "TIER1_ROUTER_FATAL | sender=%s | err=%s",
            sender_number,
            exc,
        )
        return True
