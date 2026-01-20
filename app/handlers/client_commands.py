"""
File: app/handlers/client_commands.py

Purpose:
Tier 1 Client & Admin Menu Handler

Routing rule (LOCKED):
- If webhooks resolves business context, use it (prevents cross-bot leakage)
- Otherwise fallback to prior single-store DB resolution
"""

import os
from sqlalchemy.orm import Session

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

# If you already integrated Galitos menu in client_commands, keep that logic.
# If not, you can add it later without impacting the routing fix.


# =========================
# Menus
# =========================

ADMIN_MENU_TEXT = (
    "🛠️ Admin Menu\n\n"
    "📊 Surveys\n"
    "SURVEY: <question> – Send survey (auto-closes in 24h)\n"
    "END – Close active survey early\n\n"
    "👥 Clients\n"
    "ADD CLIENT: <number>\n"
    "REMOVE CLIENT: <number>\n"
    "COUNT – Active clients\n\n"
    "✉️ Messaging\n"
    "SEND: <number> <message>\n"
    "BROADCAST: <message>\n\n"
    "⚙️ System\n"
    "PAUSE – Stop outbound messages\n"
    "RESUME – Resume outbound messages\n\n"
    "📸 Tip: Send an image to broadcast it instantly."
)

CLIENT_MENU_TEXT = (
    "👋 Welcome!\n\n"
    "📊 From time to time, you may receive a short survey.\n"
    "Please tap the buttons to respond — it only takes a second.\n\n"
    "Options\n"
    "ABOUT – Store details\n"
    "JOIN – Receive updates\n"
    "STOP – Opt out\n"
    "COMPLAINT – Log a complaint (type: Complaint: your message)\n"
    "MENU – Show this menu again\n\n"
    "For store hours or specials,\n"
    "just reply HOURS or SPECIALS."
)

FEEDBACK_ACK_TEXT = (
    "🙏 Thank you for your message.\n"
    "We’ve shared it with the manager."
)

ADMIN_ALLOWLIST = {
    n.strip()
    for n in os.getenv("OUTBOUND_TEST_ALLOWLIST", "").split(",")
    if n.strip()
}

_meta_client = MetaWhatsAppClient(settings=load_meta_settings())


def _send_text(to_number: str, text: str) -> None:
    _meta_client.send_session_message(
        to_msisdn=to_number,
        text=text,
    )


def _resolve_store_context_fallback(db: Session):
    """
    Single-store fallback: resolve context from DB, not env.
    Returns:
      (client_id, business_number_msisdn) or (None, None)
    """
    wa = (
        db.query(WhatsAppNumber)
        .filter(WhatsAppNumber.status == "active")
        .first()
    )
    if not wa:
        return None, None

    return wa.client_id, wa.destination_number


def handle_client_command(
    *,
    db,
    sender_number: str,
    message_text: str,
    msg: dict | None = None,
    resolved_client_id: str | None = None,
    resolved_business_number: str | None = None,
    resolved_phone_number_id: str | None = None,  # kept for analytics/debug if needed
) -> bool:
    is_admin = sender_number in ADMIN_ALLOWLIST

    # ✅ Prefer business-scoped routing from webhooks.py
    client_id = resolved_client_id
    business_number = resolved_business_number

    # Fallback for older flows (keeps existing behaviour)
    if not client_id or not business_number:
        client_id, business_number = _resolve_store_context_fallback(db)

    # ==================================================
    # AUTO-CLOSE SURVEY
    # ==================================================
    if business_number:
        closed = auto_close_expired_surveys(db, business_number)
        if closed:
            summary = build_survey_summary_text(db, closed)
            for admin in ADMIN_ALLOWLIST:
                _send_text(admin, summary)

    # ==================================================
    # SURVEY BUTTON RESPONSE
    # ==================================================
    if msg and msg.get("type") == "interactive":
        button_reply = (
            msg.get("interactive", {})
            .get("button_reply", {})
            .get("id")
        )

        if button_reply:
            active = get_active_survey(db, sender_number)
            if active:
                recorded = record_response(
                    db=db,
                    survey=active,
                    client_number=sender_number,
                    button_id=button_reply,
                )
                if recorded:
                    _send_text(sender_number, CUSTOMER_SURVEY_THANK_YOU_TEMPLATE)

                    if client_id:
                        log_event(
                            db=db,
                            client_id=client_id,
                            event_type="survey_response",
                            event_detail=f"survey_{active.id}",
                        )
                return True

    # ==================================================
    # NORMAL COMMAND HANDLING
    # ==================================================
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

    # =========================
    # KEYWORD: HOURS
    # =========================
    if upper == "HOURS" and not is_admin:
        if client_id:
            log_event(
                db=db,
                client_id=client_id,
                event_type="inbound_keyword",
                event_detail="keyword_hours",
            )

        _send_text(sender_number, ABOUT_TEXT)

        if client_id:
            log_event(
                db=db,
                client_id=client_id,
                event_type="hours_reply_sent",
                event_detail="keyword_hours",
            )
        return True

    # =========================
    # KEYWORD: SPECIALS
    # =========================
    if upper in ("SPECIAL", "SPECIALS", "PROMOTIONS") and not is_admin:
        if client_id:
            log_event(
                db=db,
                client_id=client_id,
                event_type="inbound_keyword",
                event_detail="keyword_specials",
            )

        _send_text(
            sender_number,
            "🛒 Today’s specials are available.\nReply MENU for more options."
        )

        if client_id:
            log_event(
                db=db,
                client_id=client_id,
                event_type="specials_reply_sent",
                event_detail="keyword_specials",
            )
        return True

    _send_text(sender_number, ADMIN_MENU_TEXT if is_admin else CLIENT_MENU_TEXT)
    return True
