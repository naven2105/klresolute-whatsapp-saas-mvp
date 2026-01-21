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


_SURVEY_TYPED_RE = re.compile(
    r"^\s*survey\s+(sentiment|frequency|helpfulness)\s*:\s*(.+)\s*$",
    re.IGNORECASE,
)


def handle_admin_command(
    *,
    db: Session,
    sender_number: str,
    message_text: str,
    admin_allowlist: set[str],
) -> bool:

    logger.info("ADMIN_CMD_ENTER | sender=%s | raw=%r", sender_number, message_text)

    if sender_number not in admin_allowlist:
        logger.info("ADMIN_CMD_REJECT | not in allowlist | sender=%s", sender_number)
        return False

    meta = get_meta_client()
    text_clean = (message_text or "").strip()
    upper = text_clean.upper()

    logger.info("ADMIN_CMD_CLEAN | clean=%r | upper=%r", text_clean, upper)

    business_number = sender_number

    # ----------------------------------
    # AUTO-CLOSE SURVEY (SAFE)
    # ----------------------------------
    try:
        closed = auto_close_expired_surveys(db, business_number)
    except Exception as exc:
        logger.error("ADMIN_CMD_AUTO_CLOSE_FAIL | error=%s", exc, exc_info=True)
        closed = None

    if closed:
        logger.info("ADMIN_CMD_AUTO_CLOSED | survey_id=%s", closed.id)
        try:
            summary = build_survey_summary_text(db, closed)
            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text=summary,
            )
            logger.info("ADMIN_CMD_AUTO_CLOSED_NOTIFY_OK | survey_id=%s", closed.id)
        except Exception as exc:
            logger.error(
                "ADMIN_CMD_AUTO_CLOSED_NOTIFY_FAIL | survey_id=%s | error=%s",
                closed.id,
                exc,
                exc_info=True,
            )

    paused = getattr(meta, "is_paused", False)
    logger.info("ADMIN_CMD_PAUSE_STATE | paused=%s", paused)

    # ==================================================
    # CLOSE SURVEY — GUARANTEED ADMIN FEEDBACK
    # ==================================================
    if upper == SURVEY_COMMAND_END:
        logger.info("ADMIN_CMD_SURVEY_CLOSE_REQUEST")

        try:
            active = get_active_survey(db, business_number)
        except Exception as exc:
            logger.error("ADMIN_CMD_GET_ACTIVE_FAIL | error=%s", exc, exc_info=True)
            active = None

        if not active:
            logger.warning("ADMIN_CMD_NO_ACTIVE_SURVEY")
            try:
                meta.send_generic_business_update_template(
                    to_msisdn=sender_number,
                    blob_text=ADMIN_SURVEY_NO_ACTIVE_TEMPLATE,
                )
                logger.info("ADMIN_CMD_NO_ACTIVE_NOTIFY_OK")
            except Exception as exc:
                logger.error("ADMIN_CMD_NO_ACTIVE_NOTIFY_FAIL | error=%s", exc, exc_info=True)
            return True

        try:
            close_survey(db, active, manual=True)
            logger.info("ADMIN_CMD_SURVEY_CLOSED | survey_id=%s", active.id)
        except Exception as exc:
            logger.error(
                "ADMIN_CMD_SURVEY_CLOSE_FAIL | survey_id=%s | error=%s",
                getattr(active, "id", None),
                exc,
                exc_info=True,
            )
            # Still try to notify admin something went wrong (without changing behaviour flow)
            try:
                meta.send_generic_business_update_template(
                    to_msisdn=sender_number,
                    blob_text="⚠️ Survey close failed (see logs).",
                )
            except Exception:
                pass
            return True

        try:
            summary = build_survey_summary_text(db, active)
        except Exception as exc:
            logger.error(
                "ADMIN_CMD_BUILD_SUMMARY_FAIL | survey_id=%s | error=%s",
                active.id,
                exc,
                exc_info=True,
            )
            summary = "⚠️ Survey closed, but summary generation failed (see logs)."

        # 1️⃣ Send summary (exception-safe)
        try:
            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text=summary,
            )
            logger.info("ADMIN_CMD_CLOSE_SUMMARY_SENT_OK | survey_id=%s", active.id)
        except Exception as exc:
            logger.error(
                "ADMIN_CMD_CLOSE_SUMMARY_SENT_FAIL | survey_id=%s | error=%s",
                active.id,
                exc,
                exc_info=True,
            )

        # 2️⃣ Explicit confirmation (exception-safe)
        try:
            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text="✅ Survey closed successfully.",
            )
            logger.info("ADMIN_CMD_CLOSE_CONFIRM_SENT_OK | survey_id=%s", active.id)
        except Exception as exc:
            logger.error(
                "ADMIN_CMD_CLOSE_CONFIRM_SENT_FAIL | survey_id=%s | error=%s",
                active.id,
                exc,
                exc_info=True,
            )

        return True

    # ==================================================
    # SURVEY START (TYPED)
    # ==================================================
    m = _SURVEY_TYPED_RE.match(text_clean)
    if m:
        survey_type = m.group(1).upper()
        question = m.group(2).strip()

        logger.info(
            "ADMIN_CMD_SURVEY_TYPED | type=%s | question=%r",
            survey_type,
            question,
        )

        try:
            started, survey = start_survey(
                db=db,
                business_number=business_number,
                question=question,
                button_set=survey_type,
            )
        except Exception as exc:
            logger.error("ADMIN_CMD_START_SURVEY_FAIL | error=%s", exc, exc_info=True)
            # ensure admin gets a reply
            try:
                meta.send_generic_business_update_template(
                    to_msisdn=sender_number,
                    blob_text="⚠️ Survey start failed (see logs).",
                )
            except Exception:
                pass
            return True

        if not started:
            logger.warning("ADMIN_CMD_SURVEY_EXISTS | survey_id=%s", survey.id)
            try:
                meta.send_generic_business_update_template(
                    to_msisdn=sender_number,
                    blob_text=ADMIN_SURVEY_ALREADY_ACTIVE_TEMPLATE.format(
                        question=survey.question,
                        hours_remaining=int(
                            (survey.ends_at - survey.started_at).total_seconds() / 3600
                        ),
                    ),
                )
                logger.info("ADMIN_CMD_SURVEY_EXISTS_NOTIFY_OK | survey_id=%s", survey.id)
            except Exception as exc:
                logger.error(
                    "ADMIN_CMD_SURVEY_EXISTS_NOTIFY_FAIL | survey_id=%s | error=%s",
                    survey.id,
                    exc,
                    exc_info=True,
                )
            return True

        buttons_def = SURVEY_BUTTON_SETS[survey_type]["buttons"]
        contacts = (
            db.query(Contact)
            .filter(~Contact.contact_number.in_(admin_allowlist))
            .all()
        )

        logger.info(
            "ADMIN_CMD_SURVEY_SEND_BEGIN | survey_id=%s | recipients=%s",
            survey.id,
            len(contacts),
        )

        sent = 0
        failed = 0

        for c in contacts:
            try:
                meta.send_interactive_button_message(
                    to_msisdn=c.contact_number,
                    header_text="🗳️ Quick question",
                    body_text=question,
                    buttons=[{"id": b["id"], "title": b["text"]} for b in buttons_def],
                )
                sent += 1
            except Exception as exc:
                failed += 1
                logger.error(
                    "ADMIN_CMD_SURVEY_SEND_FAIL | survey_id=%s | to=%s | error=%s",
                    survey.id,
                    getattr(c, "contact_number", None),
                    exc,
                    exc_info=True,
                )

        logger.info(
            "ADMIN_CMD_SURVEY_SEND_DONE | survey_id=%s | sent=%s | failed=%s",
            survey.id,
            sent,
            failed,
        )

        # Admin confirmation MUST always happen (exception-safe)
        try:
            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text=ADMIN_SURVEY_STARTED_TEMPLATE.format(question=question),
            )
            logger.info("ADMIN_CMD_SURVEY_STARTED_NOTIFY_OK | survey_id=%s", survey.id)
        except Exception as exc:
            logger.error(
                "ADMIN_CMD_SURVEY_STARTED_NOTIFY_FAIL | survey_id=%s | error=%s",
                survey.id,
                exc,
                exc_info=True,
            )

        return True

    # ==================================================
    # SURVEY START (DEFAULT)
    # ==================================================
    m2 = _SURVEY_DEFAULT_RE.match(text_clean)
    if m2:
        question = m2.group(1).strip()
        logger.info("ADMIN_CMD_SURVEY_DEFAULT | question=%r", question)

        try:
            started, survey = start_survey(
                db=db,
                business_number=business_number,
                question=question,
                button_set="SENTIMENT",
            )
        except Exception as exc:
            logger.error("ADMIN_CMD_START_SURVEY_FAIL | error=%s", exc, exc_info=True)
            try:
                meta.send_generic_business_update_template(
                    to_msisdn=sender_number,
                    blob_text="⚠️ Survey start failed (see logs).",
                )
            except Exception:
                pass
            return True

        if not started:
            logger.warning("ADMIN_CMD_SURVEY_EXISTS | survey_id=%s", survey.id)
            try:
                meta.send_generic_business_update_template(
                    to_msisdn=sender_number,
                    blob_text=ADMIN_SURVEY_ALREADY_ACTIVE_TEMPLATE.format(
                        question=survey.question,
                        hours_remaining=int(
                            (survey.ends_at - survey.started_at).total_seconds() / 3600
                        ),
                    ),
                )
                logger.info("ADMIN_CMD_SURVEY_EXISTS_NOTIFY_OK | survey_id=%s", survey.id)
            except Exception as exc:
                logger.error(
                    "ADMIN_CMD_SURVEY_EXISTS_NOTIFY_FAIL | survey_id=%s | error=%s",
                    survey.id,
                    exc,
                    exc_info=True,
                )
            return True

        buttons_def = SURVEY_BUTTON_SETS["SENTIMENT"]["buttons"]
        contacts = (
            db.query(Contact)
            .filter(~Contact.contact_number.in_(admin_allowlist))
            .all()
        )

        logger.info(
            "ADMIN_CMD_SURVEY_SEND_BEGIN | survey_id=%s | recipients=%s",
            survey.id,
            len(contacts),
        )

        sent = 0
        failed = 0

        for c in contacts:
            try:
                meta.send_interactive_button_message(
                    to_msisdn=c.contact_number,
                    header_text="🗳️ Quick question",
                    body_text=question,
                    buttons=[{"id": b["id"], "title": b["text"]} for b in buttons_def],
                )
                sent += 1
            except Exception as exc:
                failed += 1
                logger.error(
                    "ADMIN_CMD_SURVEY_SEND_FAIL | survey_id=%s | to=%s | error=%s",
                    survey.id,
                    getattr(c, "contact_number", None),
                    exc,
                    exc_info=True,
                )

        logger.info(
            "ADMIN_CMD_SURVEY_SEND_DONE | survey_id=%s | sent=%s | failed=%s",
            survey.id,
            sent,
            failed,
        )

        # Admin confirmation MUST always happen (exception-safe)
        try:
            meta.send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text=ADMIN_SURVEY_STARTED_TEMPLATE.format(question=question),
            )
            logger.info("ADMIN_CMD_SURVEY_STARTED_NOTIFY_OK | survey_id=%s", survey.id)
        except Exception as exc:
            logger.error(
                "ADMIN_CMD_SURVEY_STARTED_NOTIFY_FAIL | survey_id=%s | error=%s",
                survey.id,
                exc,
                exc_info=True,
            )

        return True

    logger.warning("ADMIN_CMD_FALLTHROUGH | unknown command | clean=%r", text_clean)
    return False
