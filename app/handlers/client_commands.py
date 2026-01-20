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
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.outbound.meta import MetaWhatsAppClient
from app.outbound.settings import load_meta_settings
from app.profiles.client_profile import ABOUT_TEXT
from app.services.contacts_service import add_contact, remove_contact
from app.services.event_logger import log_event
from app.models import WhatsAppNumber

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
    "SURVEY: <question> – Sentiment (👍 Yes / 😐 Okay / 👎 No)\n"
    "SURVEY[FREQUENCY]: <question> – Frequency (Weekly / Occasionally / First time)\n"
    "SURVEY[HELPFULNESS]: <question> – Helpfulness (Very / Somewhat / Not helpful)\n"
    "END SURVEY – Close active survey early\n\n"
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
    _meta_client.send_session_message(
        to_msisdn=to_number,
        text=text,
    )


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
    is_admin = sender_number in ADMIN_ALLOWLIST

    client_id = resolved_client_id
    business_number = resolved_business_number

    if not client_id or not business_number:
        client_id, business_number = _resolve_store_context_fallback(db)

    if business_number:
        closed = auto_close_expired_surveys(db, business_number)
        if closed:
            summary = build_survey_summary_text(db, closed)
            for admin in ADMIN_ALLOWLIST:
                _send_text(admin, summary)

    if msg and msg.get("type") == "interactive":
        button_reply = (
            msg.get("interactive", {})
            .get("button_reply", {})
            .get("id")
        )
        if button_reply:
            active = get_active_survey(db, sender_number)
            if active and record_response(
                db=db,
                survey=active,
                client_number=sender_number,
                button_id=button_reply,
            ):
                _send_text(sender_number, CUSTOMER_SURVEY_THANK_YOU_TEMPLATE)
            return True

    text = (message_text or "").strip()
    upper = text.upper()

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

    _send_text(sender_number, ADMIN_MENU_TEXT if is_admin else CLIENT_MENU_TEXT)
    return True
    