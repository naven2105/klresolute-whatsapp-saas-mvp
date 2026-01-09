"""
File: app/webhooks.py
Path: app/webhooks.py

Project: KLResolute WhatsApp SaaS MVP

Purpose:
Inbound WhatsApp webhook entrypoint.
- Parse payload
- Route to correct handler (media → admin → client)
- Upsert WhatsApp end-users into clients
- Update last_interaction_at on every inbound message
- Store survey responses (admin-triggered surveys)

IMPORTANT:
- Admin SURVEY commands are handled ONLY in admin_commands.py
- webhooks.py must NEVER send surveys
"""

import logging
import os
import re

from fastapi import APIRouter, Request, Response, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text as sql_text

from app.db import get_db
from app.handlers.admin_commands import handle_admin_command
from app.handlers.client_commands import handle_client_command
from app.handlers.media_handler import handle_media_message
from app.survey.survey_models import Survey, SurveyResponse

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

logger = logging.getLogger("webhooks")
logging.basicConfig(level=logging.INFO)

ADMIN_ALLOWLIST = {
    n.strip()
    for n in os.getenv("OUTBOUND_TEST_ALLOWLIST", "").split(",")
    if n.strip()
}


def _normalise_msisdn(raw: str | None) -> str | None:
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("0"):
        digits = "27" + digits[1:]
    if digits.startswith("27") and len(digits) >= 11:
        return digits
    return None


def _extract_message(payload: dict):
    try:
        msg = payload["entry"][0]["changes"][0]["value"]["messages"][0]
        sender = msg.get("from")
        return msg, sender
    except Exception:
        return None, None


def _upsert_client(db: Session, client_number: str) -> None:
    """
    Insert client if not exists; always update last_interaction_at.
    """
    db.execute(
        sql_text(
            """
            INSERT INTO clients (client_number, last_interaction_at)
            VALUES (:client_number, now())
            ON CONFLICT (client_number)
            DO UPDATE SET
                last_interaction_at = now(),
                updated_at = now();
            """
        ),
        {"client_number": client_number},
    )
    db.commit()


@router.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    logger.info("WhatsApp webhook received")

    try:
        payload = await request.json()
    except Exception:
        return Response(status_code=200)

    msg, sender_raw = _extract_message(payload)
    sender = _normalise_msisdn(sender_raw)

    if not msg or not sender:
        return Response(status_code=200)

    # --------------------------------------------------
    # UPSERT CLIENT (ALWAYS)
    # --------------------------------------------------
    _upsert_client(db, sender)

    # --------------------------------------------------
    # MEDIA HANDLER (ADMIN IMAGE FLOW)
    # --------------------------------------------------
    if handle_media_message(
        db=db,
        sender=sender,
        msg=msg,
        admin_allowlist=ADMIN_ALLOWLIST,
    ):
        return Response(status_code=200)

    # --------------------------------------------------
    # INTERACTIVE BUTTON RESPONSE → STORE
    # --------------------------------------------------
    if msg.get("type") == "interactive":
        interactive = msg.get("interactive", {})
        button_reply = interactive.get("button_reply")

        if button_reply:
            survey = (
                db.query(Survey)
                .filter(Survey.status == "active")
                .order_by(Survey.started_at.desc())
                .first()
            )

            if survey:
                db.add(
                    SurveyResponse(
                        survey_id=survey.id,
                        client_number=sender,
                        button_id=button_reply.get("id"),
                        tag=button_reply.get("title"),
                    )
                )
                db.commit()

        return Response(status_code=200)

    # --------------------------------------------------
    # TEXT HANDLING
    # --------------------------------------------------
    if msg.get("type") == "text":
        text = msg["text"]["body"].strip()

        # ADMIN COMMANDS (SURVEYS LIVE HERE)
        handled = handle_admin_command(
            db=db,
            sender_number=sender,
            message_text=text,
            admin_allowlist=ADMIN_ALLOWLIST,
        )

        if handled:
            return Response(status_code=200)

        # CLIENT COMMANDS
        handle_client_command(
            db=db,
            sender_number=sender,
            message_text=text,
            msg=msg,
        )

    return Response(status_code=200)
