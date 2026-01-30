from __future__ import annotations

"""
File: app/handlers/client_commands.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Tier 1 Client & Admin Handler
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.outbound.meta import MetaWhatsAppClient
from app.outbound.settings import load_meta_settings
from app.profiles.client_profile import ABOUT_TEXT
from app.services.contacts_service import add_contact, remove_contact
from app.models import WhatsAppNumber

from app.utils.admin import is_admin_message

# =========================
# Logging
# =========================
logger = logging.getLogger("client_commands")

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
# Delegate customer handler
# =========================
from app.clients.galitos.customer_commands import (
    handle_client_command as handle_customer_commands
)

# =========================
# Admin menu ONLY (legacy, kept)
# =========================
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

def _send_text(to_number: str, text: str) -> None:
    logger.info("SEND_TEXT | to=%s | text=%r", to_number, text)
    _meta_client.send_session_message(to_msisdn=to_number, text=text)


def _send_latest_special(db: Session, to_number: str, client_id) -> None:
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


def _resolve_store_context_fallback(db: Session):
    wa = (
        db.query(WhatsAppNumber)
        .filter(WhatsAppNumber.status == "active")
        .first()
    )
    if not wa:
        logger.error("NO_ACTIVE_WHATSAPP_NUMBER | fallback_store_context")
        return None, None

    return wa.client_id, wa.destination_number


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
    try:
        client_id = resolved_client_id
        business_number = resolved_business_number

        if not client_id or not business_number:
            client_id, business_number = _resolve_store_context_fallback(db)

        is_admin = (
            business_number
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

                    admins = db.execute(
                        text(
                            """
                            SELECT msisdn
                            FROM client_admins
                            WHERE client_code = :client
                              AND is_active = TRUE
                            """
                        ),
                        {"client": business_number},
                    ).scalars().all()

                    for admin in admins:
                        _send_text(admin, summary)

            except Exception as e:
                logger.exception(
                    "SURVEY_AUTO_CLOSE_FAIL | business=%s | err=%s",
                    business_number,
                    str(e),
                )

        # ----------------------------------
        # Survey button replies
        # ----------------------------------
        if msg and msg.get("type") == "interactive" and business_number:
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

        # ----------------------------------
        # Text commands
        # ----------------------------------
        upper = (message_text or "").strip().upper()

        if is_admin and upper == "MENU":
            _send_text(sender_number, ADMIN_MENU_TEXT)
            return True

        if upper == "JOIN" and not is_admin:
            added = add_contact(db, msisdn=sender_number)
            _send_text(
                sender_number,
                "You’ll now receive updates from us."
                if added
                else "You’re already receiving updates.",
            )
            return True

        if upper == "STOP" and not is_admin:
            removed = remove_contact(db, msisdn=sender_number)
            _send_text(
                sender_number,
                "You’ve been opted out."
                if removed
                else "You were not subscribed.",
            )
            return True

        if upper == "ABOUT" and not is_admin:
            _send_text(sender_number, ABOUT_TEXT)
            return True

        if upper == "HOURS" and not is_admin:
            _send_text(sender_number, ABOUT_TEXT)
            return True

        if upper in ("SPECIAL", "SPECIALS") and not is_admin:
            _send_latest_special(db, sender_number, client_id)
            return True

        # ----------------------------------
        # Delegate customer text
        # ----------------------------------
        if not is_admin:
            handled = handle_customer_commands(
                db=db,
                sender=sender_number,
                msg=msg or {"type": "text", "text": {"body": message_text or ""}},
                client_id=str(client_id) if client_id else "",
                business_msisdn=business_number,
            )
            return bool(handled)

        return False

    except Exception as e:
        logger.exception(
            "CLIENT_COMMANDS_FATAL | sender=%s | err=%s",
            sender_number,
            str(e),
        )
        return True
