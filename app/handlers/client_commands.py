from __future__ import annotations

"""
File: app/handlers/client_commands.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Tier 1 Client & Admin Menu Handler

Routing rule (LOCKED):
- If webhooks resolves business context, use it (prevents cross-bot leakage)
- Otherwise fallback to prior single-store DB resolution
"""

import os
import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.outbound.meta import MetaWhatsAppClient
from app.outbound.settings import load_meta_settings
from app.profiles.client_profile import ABOUT_TEXT
from app.services.contacts_service import add_contact, remove_contact
from app.models import WhatsAppNumber

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
# Menus
# =========================

ADMIN_MENU_TEXT = (
    "🛠️ Admin Menu\n\n"
    "📊 Surveys (button-based)\n"
    "SURVEY SENTIMENT: <question> – Sentiment (👍 Yes / 😐 Okay / 👎 No)\n"
    "SURVEY FREQUENCY: <question> – Frequency (Weekly / Occasionally / First time)\n"
    "SURVEY HELPFULNESS: <question> – Helpfulness (Very helpful / Somewhat / Not helpful)\n"
    "END SURVEY – Close active survey\n\n"
    "👥 Clients\n"
    "ADD CLIENT: <number>\n"
    "REMOVE CLIENT: <number>\n"
    "COUNT – Active clients\n\n"
    "✉️ Messaging\n"
    "SEND: <number> <message>\n"
    "BROADCAST: <message>  (text only)\n\n"
    "🖼️ Specials\n"
    "Send image + caption – Updates specials (push + replay)\n\n"
    "⚙️ System\n"
    "PAUSE – Stop outbound messages\n"
    "RESUME – Resume outbound messages"
)

CLIENT_MENU_TEXT = (
    "📋 MENU\n\n"
    "👋 Welcome!\n\n"
    "Options\n"
    "\"ABOUT\" – Store information\n"
    "\"JOIN\" – Receive store updates\n"
    "\"STOP\" – Opt out of updates\n"
    "\"FEEDBACK\" – Type: FEEDBACK: your message\n"
    "\"MENU\" – Show this menu again\n"
    "\"HOURS\" – Store hours\n"
    "\"SPECIALS\" – Today’s specials\n\n"
    "📊 From time to time, you may receive a short survey.\n"
    "Please tap the buttons to respond — it only takes a second."
)

ADMIN_ALLOWLIST = {
    n.strip()
    for n in os.getenv("OUTBOUND_TEST_ALLOWLIST", "").split(",")
    if n.strip()
}

_meta_client = MetaWhatsAppClient(settings=load_meta_settings())


# =========================
# Helpers
# =========================

def _send_text(to_number: str, text: str) -> None:
    logger.info("SEND_TEXT | to=%s | text=%r", to_number, text)
    _meta_client.send_session_message(
        to_msisdn=to_number,
        text=text,
    )


def _send_latest_special(db: Session, to_number: str, client_id) -> None:
    logger.info("SEND_SPECIAL | to=%s | client_id=%s", to_number, client_id)

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
        logger.info("NO_SPECIAL_FOUND | to=%s", to_number)
        _send_text(to_number, "No specials are available right now.")
        return

    logger.info("SPECIAL_FOUND | to=%s | media_id=%s", to_number, row["media_id"])
    _meta_client.send_image_message(
        to_msisdn=to_number,
        media_id=row["media_id"],
        caption=row["caption"],
    )


def _resolve_store_context_fallback(db: Session):
    logger.warning("FALLBACK_STORE_CONTEXT")
    wa = (
        db.query(WhatsAppNumber)
        .filter(WhatsAppNumber.status == "active")
        .first()
    )
    if not wa:
        logger.error("NO_ACTIVE_WHATSAPP_NUMBER")
        return None, None

    return wa.client_id, wa.destination_number


# =========================
# Main handler
# =========================

def handle_client_command(
    *,
    db,
    sender_number: str,
    message_text: str,
    msg: dict | None = None,
    resolved_client_id: str | None = None,
    resolved_business_number: str | None = None,
    resolved_phone_number_id: str | None = None,
) -> bool:

    logger.info(
        "CLIENT_CMD_ENTER | sender=%s | text=%r | msg_type=%s",
        sender_number,
        message_text,
        msg.get("type") if msg else None,
    )

    is_admin = sender_number in ADMIN_ALLOWLIST

    client_id = resolved_client_id
    business_number = resolved_business_number

    if not client_id or not business_number:
        client_id, business_number = _resolve_store_context_fallback(db)

    # ----------------------------------
    # Auto-close surveys (admin notify)
    # ----------------------------------
    if business_number:
        closed = auto_close_expired_surveys(db, business_number)
        if closed:
            logger.info("SURVEY_AUTO_CLOSED | survey_id=%s", closed.id)
            summary = build_survey_summary_text(db, closed)
            for admin in ADMIN_ALLOWLIST:
                _send_text(admin, summary)

    # ----------------------------------
    # Survey button replies
    # ----------------------------------
    if msg and msg.get("type") == "interactive":
        button_reply = (
            msg.get("interactive", {})
            .get("button_reply", {})
            .get("id")
        )

        logger.info(
            "INTERACTIVE_REPLY | sender=%s | button_id=%s",
            sender_number,
            button_reply,
        )

        if button_reply and business_number:
            active = get_active_survey(db, business_number)
            if active:
                ok = record_response(
                    db=db,
                    survey=active,
                    client_number=sender_number,
                    button_id=button_reply,
                )
                logger.info(
                    "SURVEY_RESPONSE_RECORDED | ok=%s | survey_id=%s",
                    ok,
                    active.id,
                )
                if ok:
                    _send_text(sender_number, CUSTOMER_SURVEY_THANK_YOU_TEMPLATE)
            else:
                logger.warning("NO_ACTIVE_SURVEY_FOR_RESPONSE")

            return True

    # ----------------------------------
    # Text commands
    # ----------------------------------
    text = (message_text or "").strip()
    upper = text.upper()

    logger.info("TEXT_CMD | sender=%s | upper=%s | admin=%s", sender_number, upper, is_admin)

    if upper == "MENU" or not upper:
        _send_text(sender_number, ADMIN_MENU_TEXT if is_admin else CLIENT_MENU_TEXT)
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

    logger.info("FALLBACK_MENU | sender=%s | admin=%s", sender_number, is_admin)
    _send_text(sender_number, ADMIN_MENU_TEXT if is_admin else CLIENT_MENU_TEXT)
    return True
