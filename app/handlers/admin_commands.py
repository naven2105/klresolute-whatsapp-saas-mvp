from __future__ import annotations

"""
File: app/handlers/admin_commands.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
All Tier-1 admin commands including surveys and broadcasts.

Admin UX polish:
- Clear, factual confirmations
- Neutral admin notifications
- No misleading prompts
"""

import re
import logging
from sqlalchemy.orm import Session

from app.models import Contact
from app.outbound.factory import get_meta_client
from app.services.contacts_service import add_contact, remove_contact

# =========================
# Logging
# =========================

logger = logging.getLogger("admin_commands")
logger.setLevel(logging.INFO)

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


# Accept flexible admin survey syntax (case-insensitive):
# - SURVEY: <question>
# - SURVEY SENTIMENT: <question>
# - SURVEY FREQUENCY: <question>
# - SURVEY HELPFULNESS: <question>
_SURVEY_TYPED_RE = re.compile(
    r"^\s*survey\s+(sentiment|frequency|helpfulness)\s*:\s*(.+)\s*$",
    re.IGNORECASE,
)
_SURVEY_DEFAULT_RE = re.compile(
    r"^\s*survey\s*:\s*(.+)\s*$",
    re.IGNORECASE,
)


def handle_admin_command(
    *,
    db: Session,
    sender_number: str,
    message_text: str,
    admin_allowlist: set[str],
) -> bool:

    logger.info(
        "ADMIN_CMD_ENTER | sender=%s | raw=%r",
        sender_number,
        message_text,
    )

    # ----------------------------------
    # Admin gate (SECURITY)
    # ----------------------------------
    if sender_number not in admin_allowlist:
        logger.info("ADMIN_CMD_REJECT | sender not in allowlist")
        return False

    meta = get_meta_client()
    text_clean = (message_text or "").strip()
    upper = text_clean.upper()

    logger.info(
        "ADMIN_CMD_CLEAN | clean=%r | upper=%r",
        text_clean,
        upper,
    )

    # ----------------------------------
    # Resolve business identity ONCE
    # ----------------------------------
    business_number = sender_number

    # ----------------------------------
    # AUTO-CLOSE SURVEY (SAFE)
    # ----------------------------------
    closed = auto_close_expired_surveys(db, business_number)
    if closed:
        logger.info("ADMIN_CMD_SURVEY_AUTO_CLOSED | survey_id=%s", closed.id)
        summary = build_survey_summary_text(db, closed)
        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text=summary,
        )

    # ----------------------------------
    # SAFE PAUSE FLAG
    # ----------------------------------
    paused = getattr(meta, "is_paused", False)
    logger.info("ADMIN_CMD_PAUSE_STATE | paused=%s", paused)

    # ==================================================
    # END SURVEY
    # ==================================================

    if upper == SURVEY_COMMAND_END:
        logger.info("ADMIN_CMD_MATCH | END SURVEY")
        active = get_active_survey(db, business_number)
        if not active:
            logger.info("ADMIN_CMD_END_SURVEY | no active survey")
            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text=ADMIN_SURVEY_NO_ACTIVE_TEMPLATE,
            )
            return True

        close_survey(db, active, manual=True)
        logger.info("ADMIN_CMD_END_SURVEY | closed survey_id=%s", active.id)
        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text=build_survey_summary_text(db, active),
        )
        return True

    # ==================================================
    # SURVEY (typed)
    # ==================================================

    m = _SURVEY_TYPED_RE.match(text_clean)
    if m:
        survey_type = m.group(1).upper()
        question = (m.group(2) or "").strip()

        logger.info(
            "ADMIN_CMD_SURVEY_TYPED | type=%s | question=%r",
            survey_type,
            question,
        )

        if not question:
            logger.warning("ADMIN_CMD_SURVEY_TYPED | empty question")
            return False

        started, survey = start_survey(
            db=db,
            business_number=business_number,
            question=question,
            button_set=survey_type,
        )

        if not started:
            logger.info(
                "ADMIN_CMD_SURVEY_EXISTS | survey_id=%s",
                survey.id,
            )
            remaining = max(
                0,
                int((survey.ends_at - survey.started_at).total_seconds() / 3600),
            )
            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text=ADMIN_SURVEY_ALREADY_ACTIVE_TEMPLATE.format(
                    question=survey.question,
                    hours_remaining=remaining,
                ),
            )
            return True

        buttons_def = SURVEY_BUTTON_SETS[survey_type]["buttons"]
        contacts = (
            db.query(Contact)
            .filter(~Contact.contact_number.in_(admin_allowlist))
            .all()
        )

        logger.info(
            "ADMIN_CMD_SURVEY_SEND | survey_id=%s | recipients=%s",
            survey.id,
            len(contacts),
        )

        for c in contacts:
            try:
                meta.send_interactive_button_message(
                    to_msisdn=c.contact_number,
                    header_text="🗳️ Quick question",
                    body_text=question,
                    buttons=[{"id": b["id"], "title": b["text"]} for b in buttons_def],
                )
            except Exception as exc:
                logger.error(
                    "ADMIN_CMD_SURVEY_SEND_FAIL | to=%s | error=%s",
                    c.contact_number,
                    exc,
                    exc_info=True,
                )

        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text=ADMIN_SURVEY_STARTED_TEMPLATE.format(question=question),
        )
        return True

    # ==================================================
    # SURVEY (default sentiment)
    # ==================================================

    m2 = _SURVEY_DEFAULT_RE.match(text_clean)
    if m2:
        question = (m2.group(1) or "").strip()
        logger.info(
            "ADMIN_CMD_SURVEY_DEFAULT | question=%r",
            question,
        )

        if not question:
            logger.warning("ADMIN_CMD_SURVEY_DEFAULT | empty question")
            return False

        started, survey = start_survey(
            db=db,
            business_number=business_number,
            question=question,
            button_set="SENTIMENT",
        )

        if not started:
            logger.info(
                "ADMIN_CMD_SURVEY_EXISTS | survey_id=%s",
                survey.id,
            )
            remaining = max(
                0,
                int((survey.ends_at - survey.started_at).total_seconds() / 3600),
            )
            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text=ADMIN_SURVEY_ALREADY_ACTIVE_TEMPLATE.format(
                    question=survey.question,
                    hours_remaining=remaining,
                ),
            )
            return True

        buttons_def = SURVEY_BUTTON_SETS["SENTIMENT"]["buttons"]
        contacts = (
            db.query(Contact)
            .filter(~Contact.contact_number.in_(admin_allowlist))
            .all()
        )

        logger.info(
            "ADMIN_CMD_SURVEY_SEND | survey_id=%s | recipients=%s",
            survey.id,
            len(contacts),
        )

        for c in contacts:
            try:
                meta.send_interactive_button_message(
                    to_msisdn=c.contact_number,
                    header_text="🗳️ Quick question",
                    body_text=question,
                    buttons=[{"id": b["id"], "title": b["text"]} for b in buttons_def],
                )
            except Exception as exc:
                logger.error(
                    "ADMIN_CMD_SURVEY_SEND_FAIL | to=%s | error=%s",
                    c.contact_number,
                    exc,
                    exc_info=True,
                )

        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text=ADMIN_SURVEY_STARTED_TEMPLATE.format(question=question),
        )
        return True

    # ==================================================
    # EXISTING COMMANDS
    # ==================================================

    if upper == "PAUSE":
        logger.info("ADMIN_CMD_MATCH | PAUSE")
        if hasattr(meta, "is_paused"):
            meta.is_paused = True
            db.commit()
        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text="Outbound messaging is now PAUSED.",
        )
        return True

    if upper == "RESUME":
        logger.info("ADMIN_CMD_MATCH | RESUME")
        if hasattr(meta, "is_paused"):
            meta.is_paused = False
            db.commit()
        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text="Outbound messaging has been RESUMED.",
        )
        return True

    if upper == "COUNT":
        logger.info("ADMIN_CMD_MATCH | COUNT")
        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text=f"Active clients: {db.query(Contact).count()}",
        )
        return True

    if upper.startswith("ADD CLIENT:"):
        logger.info("ADMIN_CMD_MATCH | ADD CLIENT")
        msisdn = _normalise_msisdn(message_text.split(":", 1)[1])
        if not msisdn:
            logger.warning("ADMIN_CMD_ADD_CLIENT | invalid msisdn")
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
        logger.info("ADMIN_CMD_MATCH | REMOVE CLIENT")
        msisdn = _normalise_msisdn(message_text.split(":", 1)[1])
        if not msisdn:
            logger.warning("ADMIN_CMD_REMOVE_CLIENT | invalid msisdn")
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
        logger.info("ADMIN_CMD_MATCH | SEND")
        if paused:
            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text="Outbound messaging is PAUSED.",
            )
            return True

        try:
            _, body = message_text.split(":", 1)
            raw, text_msg = body.strip().split(maxsplit=1)
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
                blob_text=text_msg.strip(),
            )

            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text=f"Message sent to {msisdn}.",
            )
        except Exception as exc:
            logger.error("ADMIN_CMD_SEND_FAIL | error=%s", exc, exc_info=True)
            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text="SEND failed. Format: SEND: <number> <message>",
            )

        return True

    if upper.startswith("BROADCAST"):
        logger.info("ADMIN_CMD_MATCH | BROADCAST")
        if paused:
            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text="Outbound messaging is PAUSED.",
            )
            return True

        text_msg = ""
        if ":" in message_text:
            text_msg = message_text.split(":", 1)[1].strip()

        contacts = (
            db.query(Contact)
            .filter(~Contact.contact_number.in_(admin_allowlist))
            .all()
        )

        for c in contacts:
            if text_msg:
                meta.send_generic_business_update_template(
                    to_msisdn=c.contact_number,
                    blob_text=text_msg,
                )

        meta.send_generic_business_update_template(
            to_msisdn=sender_number,
            blob_text=f"Broadcast sent to {len(contacts)} clients.",
        )
        return True

    logger.warning(
        "ADMIN_CMD_FALLTHROUGH | unknown command | clean=%r",
        text_clean,
    )
    return False
