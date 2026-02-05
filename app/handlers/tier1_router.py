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

Tier-1 Routing Rule (LOCKED):
- MUST resolve client_id (UUID) before delegating to downstream handlers.
- MUST NOT allow customer handlers to run with missing client_id.
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


# =================================================
# Helpers
# =================================================

def _send_text(to_number: str, text_msg: str) -> None:
    logger.info("SEND_TEXT | to=%s | text=%r", to_number, text_msg)
    _meta_client.send_session_message(to_msisdn=to_number, text=text_msg)


def _resolve_client_id_by_business_number(
    db: Session,
    *,
    business_number: str,
) -> str | None:
    """
    Resolve client_id (UUID) using the WhatsApp business destination number.

    Source of truth:
    public.whatsapp_numbers.destination_number -> public.whatsapp_numbers.client_id (UUID)
    """
    if not business_number:
        logger.error("CLIENT_RESOLUTION_FAILED | reason=missing_business_number")
        return None

    try:
        row = (
            db.execute(
                text(
                    """
                    SELECT client_id
                    FROM whatsapp_numbers
                    WHERE destination_number = :business
                    LIMIT 1
                    """
                ),
                {"business": business_number},
            )
            .mappings()
            .first()
        )

        if not row or not row.get("client_id"):
            logger.error(
                "CLIENT_RESOLUTION_FAILED | reason=client_not_found | business=%s",
                business_number,
            )
            return None

        client_id = str(row["client_id"]).strip()
        logger.info(
            "CLIENT_RESOLVED | client_id=%s | business=%s",
            client_id,
            business_number,
        )
        return client_id

    except Exception as exc:
        logger.exception(
            "CLIENT_RESOLUTION_FAILED | reason=exception | business=%s | err=%s",
            business_number,
            exc,
        )
        return None


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


def _ensure_client_contact(
    db: Session,
    *,
    client_id: str,
    contact_number: str,
) -> None:
    """
    Silent "JOIN" (implicit):
    - If no row exists: insert is_opted_out = FALSE
    - If row exists and is_opted_out = TRUE: do nothing
    - If row exists and is_opted_out = FALSE: do nothing

    NOTE:
    - client_id is UUID (string), not int.
    """
    if not client_id:
        logger.error(
            "SILENT_JOIN_GUARD_FAIL | reason=missing_client_id | contact=%s",
            contact_number,
        )
        return

    try:
        row = (
            db.execute(
                text(
                    """
                    SELECT is_opted_out
                    FROM client_contacts
                    WHERE client_id = :client_id
                      AND contact_number = :contact_number
                    LIMIT 1
                    """
                ),
                {"client_id": client_id, "contact_number": contact_number},
            )
            .mappings()
            .first()
        )

        if row:
            if bool(row.get("is_opted_out")) is True:
                logger.info(
                    "SILENT_JOIN_SKIPPED_OPTED_OUT | client_id=%s | contact=%s",
                    client_id,
                    contact_number,
                )
                return

            logger.info(
                "SILENT_JOIN_EXISTS | client_id=%s | contact=%s",
                client_id,
                contact_number,
            )
            return

        db.execute(
            text(
                """
                INSERT INTO client_contacts (client_id, contact_number, is_opted_out, created_at)
                VALUES (:client_id, :contact_number, FALSE, now())
                """
            ),
            {"client_id": client_id, "contact_number": contact_number},
        )
        db.commit()

        logger.info(
            "SILENT_JOIN_INSERTED | client_id=%s | contact=%s",
            client_id,
            contact_number,
        )

    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        logger.exception(
            "SILENT_JOIN_FAIL | client_id=%s | contact=%s | err=%s",
            client_id,
            contact_number,
            exc,
        )


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

        # -------------------------------------------------
        # Resolve client_id (UUID) once, in Tier-1 (LOCKED)
        # -------------------------------------------------
        client_id: str | None = None
        if resolved_client_id and str(resolved_client_id).strip():
            client_id = str(resolved_client_id).strip()
            logger.info(
                "CLIENT_RESOLVED | client_id=%s | source=resolved_client_id",
                client_id,
            )
        else:
            client_id = _resolve_client_id_by_business_number(
                db,
                business_number=business_number or "",
            )

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

            return False

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
        # Customer path: require client_id + silent join + delegate
        # -------------------------------------------------
        if not is_admin:
            if not client_id:
                logger.error(
                    "CLIENT_RESOLUTION_FAILED | reason=missing_client_id_before_customer_dispatch "
                    "| sender=%s | business=%s",
                    sender_number,
                    business_number,
                )
                # Hard stop: no fallback menu, no customer handler without client_id.
                return True

            _ensure_client_contact(
                db,
                client_id=client_id,
                contact_number=sender_number,
            )

            return bool(
                handle_customer_commands(
                    db=db,
                    sender=sender_number,
                    msg=msg or {"type": "text", "text": {"body": message_text or ""}},
                    client_id=client_id,
                    business_msisdn=business_number or "",
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
