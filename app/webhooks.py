"""
File: app/webhooks.py
Path: app/webhooks.py

Project: KLResolute WhatsApp SaaS MVP

Purpose:
Inbound WhatsApp webhook entrypoint.
- Parse payload
- Route to correct handler (media → admin → client)
- Store survey responses
"""

import logging
import os
import re

from fastapi import APIRouter, Request, Response, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.handlers.admin_commands import handle_admin_command
from app.handlers.client_commands import handle_client_command
from app.handlers.media_handler import handle_media_message
from app.outbound.meta import MetaWhatsAppClient
from app.outbound.settings import MetaWhatsAppSettings
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
    # MEDIA HANDLER
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
            button_id = button_reply.get("id")
            button_title = button_reply.get("title")

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
                        button_id=button_id,
                        tag=button_title,
                    )
                )
                db.commit()

        return Response(status_code=200)

    # --------------------------------------------------
    # TEXT HANDLING
    # --------------------------------------------------
    if msg.get("type") == "text":
        text = msg["text"]["body"].strip()

        # ===============================================
        # ADMIN: SEND SURVEY
        # ===============================================
        if sender in ADMIN_ALLOWLIST and text.upper().startswith("SURVEY:"):
            question = text.split("SURVEY:", 1)[1].strip()

            if question:
                settings = MetaWhatsAppSettings(
                    api_version=os.getenv("META_WA_API_VERSION"),
                    access_token=os.getenv("META_WA_ACCESS_TOKEN"),
                    phone_number_id=os.getenv("META_WA_PHONE_NUMBER_ID"),
                )
                meta = MetaWhatsAppClient(settings)

                # Tier-1: all known clients
                rows = db.execute(
                    "SELECT DISTINCT client_number FROM clients"
                ).fetchall()

                for (client_number,) in rows:
                    meta.send_interactive_button_message(
                        to_msisdn=client_number,
                        body_text=question,
                        buttons=[
                            {"id": "YES", "title": "Yes"},
                            {"id": "NO", "title": "No"},
                            {"id": "NOT_SURE", "title": "Not sure"},
                        ],
                    )

            return Response(status_code=200)

        # Existing behaviour
        handle_admin_command(
            db=db,
            sender_number=sender,
            message_text=text,
            admin_allowlist=ADMIN_ALLOWLIST,
        )

        handle_client_command(
            db=db,
            sender_number=sender,
            message_text=text,
            msg=msg,
        )

    return Response(status_code=200)
