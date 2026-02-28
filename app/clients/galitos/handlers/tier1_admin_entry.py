from __future__ import annotations

"""
File: app/clients/galitos/handlers/tier1_admin_entry.py
Path: app/clients/galitos/handlers/tier1_admin_entry.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Handle Tier-1 Galitos ADMIN flow only.

GUARDS (LOCKED):
- Admin-only entry
- Must NOT handle customer flow
- Must NOT intercept YES / NO
- Admin must ALWAYS receive a response
- MUST NEVER raise exceptions
- MUST fail safe and log clearly (Render-friendly)
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.messaging.client_messenger import send_message
from app.modules.survey.handler import handle as survey_handler  # kept (no removals)

# Survey imports
from app.modules.survey.survey_service import (
    auto_close_expired_surveys,
    get_active_survey,
)
from app.modules.survey.service import record_response
from app.modules.survey.summary import build_survey_summary_text

# Delegate admin survey commands
from app.clients.galitos.handlers.admin_surveys import handle_admin_surveys

from app.menus.admin.galitos_admin_menu import GALITOS_ADMIN_MENU

logger = logging.getLogger("handlers.tier1.admin")


# -------------------------------------------------
# Helpers
# -------------------------------------------------

def _format_admin_menu(menu: dict) -> str:
    text_block = menu.get("text")
    if isinstance(text_block, str) and text_block.strip():
        return text_block.strip()

    lines: list[str] = []

    title = menu.get("title")
    if title:
        lines.append(title)
        lines.append("")

    for section in menu.get("sections", []):
        section_title = section.get("title")
        if section_title:
            lines.append(section_title)

        commands = section.get("commands", [])
        for cmd in commands:
            lines.append(f"• {cmd}")

        lines.append("")

    return "\n".join(lines).strip()


def _send_text(
    *,
    business_msisdn: str,
    to_number: str,
    text_msg: str,
    db: Session,
) -> None:
    try:
        send_message(
            db=db,
            business_msisdn=business_msisdn,
            to_number=to_number,
            text=text_msg,
        )
    except Exception:
        logger.exception(
            "ADMIN_SEND_FAIL | business=%s | to=%s",
            business_msisdn,
            to_number,
        )


def _admin_numbers(db: Session, *, business_msisdn: str) -> list[str]:
    try:
        return (
            db.execute(
                text(
                    """
                    SELECT ca.msisdn
                    FROM client_admins ca
                    JOIN whatsapp_numbers w
                      ON UPPER(ca.client_code) = (
                          SELECT UPPER(c.client_name)
                          FROM clients c
                          WHERE c.client_id = w.client_id
                          LIMIT 1
                      )
                    WHERE w.destination_number = :business
                      AND ca.is_active = TRUE
                    """
                ),
                {"business": business_msisdn},
            )
            .scalars()
            .all()
        )
    except Exception:
        logger.exception(
            "ADMIN_LOOKUP_FAIL | business=%s",
            business_msisdn,
        )
        return []


# -------------------------------------------------
# Public entry
# -------------------------------------------------

def handle_admin_entry(
    *,
    db: Session,
    sender_number: str,
    message_text: str,
    msg: dict | None,
    business_msisdn: str | None,
) -> bool:
    try:
        if not business_msisdn:
            logger.error(
                "ADMIN_BLOCKED | reason=missing_business_msisdn | sender=%s",
                sender_number,
            )
            return True

        upper = (message_text or "").strip().upper()

        # ----------------------------------
        # Survey auto-close
        # ----------------------------------
        try:
            closed = auto_close_expired_surveys(db, business_msisdn)
            if closed:
                summary = build_survey_summary_text(db, closed)
                for admin in _admin_numbers(db, business_msisdn=business_msisdn):
                    _send_text(
                        business_msisdn=business_msisdn,
                        to_number=admin,
                        text_msg=summary,
                        db=db,
                    )
        except Exception:
            logger.exception(
                "ADMIN_SURVEY_AUTOCLOSE_FAIL | business=%s",
                business_msisdn,
            )

        # ----------------------------------
        # Survey button replies (FIXED: template + interactive)
        # ----------------------------------
        if msg:
            try:
                button_id = None

                if msg.get("type") == "interactive":
                    button_id = (
                        msg.get("interactive", {})
                        .get("button_reply", {})
                        .get("id")
                    )

                elif msg.get("type") == "button":
                    button_id = msg.get("button", {}).get("payload")

                if button_id:
                    active = get_active_survey(db, business_msisdn)
                    if active and record_response(
                        db=db,
                        survey=active,
                        client_number=sender_number,
                        button_id=button_id,
                    ):
                        _send_text(
                            business_msisdn=business_msisdn,
                            to_number=sender_number,
                            text_msg="Thank you for your response.",
                            db=db,
                        )
                    return True

            except Exception:
                logger.exception(
                    "ADMIN_SURVEY_RESPONSE_FAIL | sender=%s",
                    sender_number,
                )
                return True

        # ----------------------------------
        # Survey admin commands (text)
        # ----------------------------------
        if handle_admin_surveys(
            db=db,
            sender_number=sender_number,
            message_text=message_text,
            business_msisdn=business_msisdn,
        ):
            return True

        # ----------------------------------
        # Admin menu
        # ----------------------------------
        if upper == "MENU":
            _send_text(
                business_msisdn=business_msisdn,
                to_number=sender_number,
                text_msg=_format_admin_menu(GALITOS_ADMIN_MENU),
                db=db,
            )
            return True

        # ----------------------------------
        # Fallback (always respond)
        # ----------------------------------
        _send_text(
            business_msisdn=business_msisdn,
            to_number=sender_number,
            text_msg=_format_admin_menu(GALITOS_ADMIN_MENU),
            db=db,
        )
        return True

    except Exception:
        logger.exception(
            "ADMIN_ENTRY_FATAL | sender=%s",
            sender_number,
        )
        return True