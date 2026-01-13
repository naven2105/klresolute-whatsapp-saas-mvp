"""
File: app/handlers/admin_commands.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
All Tier-1 admin commands including IMAGE BROADCAST.

Admin UX polish:
- Clear, factual confirmations
- Neutral admin notifications
- No misleading prompts
"""

import re
from sqlalchemy.orm import Session

from app.models import Contact
from app.outbound.factory import get_meta_client
from app.services.contacts_service import add_contact, remove_contact

# =========================
# Survey imports
# =========================
from app.survey import (
    start_survey,
    get_active_survey,
    close_survey,
    build_survey_summary_text,
    auto_close_expired_surveys,
    SUPPORTED_SURVEY_COMMANDS,
    SURVEY_COMMAND_END,
)
from app.survey.survey_constants import (
    ADMIN_SURVEY_STARTED_TEMPLATE,
    ADMIN_SURVEY_ALREADY_ACTIVE_TEMPLATE,
    ADMIN_SURVEY_NO_ACTIVE_TEMPLATE,
    SURVEY_BUTTON_SETS,
)


def _normalise_msisdn(raw: str | None) -> str | None:
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("0"):
        digits = "27" + digits[1:]
    if digits.startswith("27") and len(digits) >= 11:
        return digits
    return None


def handle_admin_command(
    *,
    db: Session,
    sender_number: str,
    message_text: str,
    admin_allowlist: set[str],
) -> bool:

    # ----------------------------------
    # Admin gate (SECURITY)
    # ----------------------------------
    if sender_number not in admin_allowlist:
        return False

    meta = get_meta_client()
    text_clean = message_text.strip()
    upper = text_clean.upper()

    # =========================
    # Guard: invalid survey usage
    # =========================
    if text_clean.lower().startswith("survey") and not text_clean.lower().startswith("survey["):
        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text=(
                "ℹ️ Survey command format\n\n"
                "To start a survey, choose a type and include your question:\n\n"
                "survey[sentiment]: <your question>\n"
                "Buttons: 👍 Yes | 😐 Okay | 👎 No\n\n"
                "survey[frequency]: <your question>\n"
                "Buttons: Weekly | Occasionally | First time\n\n"
                "survey[helpfulness]: <your question>\n"
                "Buttons: Very helpful | Somewhat helpful | Not helpful\n\n"
                "Example:\n"
                "survey[sentiment]: How were the apples today?"
            ),
        )
        return True

    # ----------------------------------
    # Resolve business identity ONCE
    # ----------------------------------
    business_number = sender_number

    # ----------------------------------
    # AUTO-CLOSE SURVEY (SAFE)
    # ----------------------------------
    closed = auto_close_expired_surveys(db, business_number)
    if closed:
        summary = build_survey_summary_text(db, closed)
        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text=summary,
        )

    # ----------------------------------
    # SAFE PAUSE FLAG
    # ----------------------------------
    paused = getattr(meta, "is_paused", False)

    # ==================================================
    # SURVEYS (Tier 1)
    # ==================================================

    if upper == SURVEY_COMMAND_END:
        active = get_active_survey(db, business_number)
        if not active:
            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text=ADMIN_SURVEY_NO_ACTIVE_TEMPLATE,
            )
            return True

        close_survey(db, active, manual=True)
        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text=build_survey_summary_text(db, active),
        )
        return True

    for command, button_set in SUPPORTED_SURVEY_COMMANDS.items():
        if upper.startswith(command):
            question = message_text.replace(command, "", 1).strip(": ").strip()

            if not question:
                meta.send_generic_business_update_template(
                    to_msisdn=sender_number,
                    blob_text="Survey question cannot be empty.",
                )
                return True

            started, survey = start_survey(
                db=db,
                business_number=business_number,
                question=question,
                button_set=button_set,
            )

            if not started:
                remaining = max(
                    0,
                    int(
                        (survey.ends_at - survey.started_at).total_seconds() / 3600
                    ),
                )
                meta.send_generic_business_update_template(
                    to_msisdn=sender_number,
                    blob_text=ADMIN_SURVEY_ALREADY_ACTIVE_TEMPLATE.format(
                        question=survey.question,
                        hours_remaining=remaining,
                    ),
                )
                return True

            buttons_def = SURVEY_BUTTON_SETS[button_set]["buttons"]

            contacts = (
                db.query(Contact)
                .filter(~Contact.contact_number.in_(admin_allowlist))
                .all()
            )

            for c in contacts:
                meta.send_interactive_button_message(
                    to_msisdn=c.contact_number,
                    header_text="🗳️ Quick question",
                    body_text=question,
                    buttons=[
                        {"id": b["id"], "title": b["text"]}
                        for b in buttons_def
                    ],
                )

            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text=ADMIN_SURVEY_STARTED_TEMPLATE.format(
                    question=question,
                ),
            )
            return True

    # ==================================================
    # EXISTING COMMANDS
    # ==================================================

    if upper == "PAUSE":
        if hasattr(meta, "is_paused"):
            meta.is_paused = True
            db.commit()
            paused = True
        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text="Outbound messaging is now PAUSED.",
        )
        return True

    if upper == "RESUME":
        if hasattr(meta, "is_paused"):
            meta.is_paused = False
            db.commit()
            paused = False
        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text="Outbound messaging has been RESUMED.",
        )
        return True

    if upper == "COUNT":
        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text=f"Active clients: {db.query(Contact).count()}",
        )
        return True

    if upper.startswith("ADD CLIENT:"):
        msisdn = _normalise_msisdn(message_text.split(":", 1)[1])
        if not msisdn:
            return True

        added = add_contact(db, msisdn=msisdn)
        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text=(
                f"Client {msisdn} added."
                if added
                else f"Client {msisdn} already exists."
            ),
        )
        return True

    if upper.startswith("REMOVE CLIENT:"):
        msisdn = _normalise_msisdn(message_text.split(":", 1)[1])
        if not msisdn:
            return True

        removed = remove_contact(db, msisdn=msisdn)
        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text=(
                f"Client {msisdn} removed."
                if removed
                else f"Client {msisdn} not found."
            ),
        )
        return True

    if upper.startswith("SEND:"):
        if paused:
            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text="Outbound messaging is PAUSED.",
            )
            return True

        try:
            _, body = message_text.split(":", 1)
            raw, text = body.strip().split(maxsplit=1)
            msisdn = _normalise_msisdn(raw)

            contact = (
                db.query(Contact)
                .filter(Contact.contact_number == msisdn)
                .one_or_none()
            )
            if not contact:
                raise ValueError()

            meta.send_generic_business_update_template(
                to_msisdn=msisdn,
                blob_text=text.strip(),
            )

            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text=f"Message sent to {msisdn}.",
            )
        except Exception:
            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text="SEND failed. Format: SEND: <number> <message>",
            )

        return True

    if upper.startswith("BROADCAST"):
        if paused:
            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text="Outbound messaging is PAUSED.",
            )
            return True

        text = ""
        if ":" in message_text:
            text = message_text.split(":", 1)[1].strip()

        contacts = (
            db.query(Contact)
            .filter(~Contact.contact_number.in_(admin_allowlist))
            .all()
        )

        sent = 0
        for c in contacts:
            if text:
                meta.send_generic_business_update_template(
                    to_msisdn=c.contact_number,
                    blob_text=text,
                )
            sent += 1

        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text=f"Broadcast sent to {sent} clients.",
        )
        return True

    return False
