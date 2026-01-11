"""
File: app/webhooks.py
Project: KLResolute WhatsApp SaaS MVP
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
from app.outbound.meta import MetaWhatsAppClient
from app.outbound.settings import MetaWhatsAppSettings
from app.survey.survey_models import Survey, SurveyResponse
from app.survey.auto_close import auto_close_expired_surveys

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
        return msg, msg.get("from")
    except Exception:
        return None, None


def _extract_business_number(payload: dict) -> str | None:
    """
    Returns the WhatsApp Business phone_number_id from webhook metadata.
    This is required for survey auto-close logic.
    """
    try:
        return payload["entry"][0]["changes"][0]["value"]["metadata"]["phone_number_id"]
    except Exception:
        return None


def _upsert_client(db: Session, client_number: str) -> None:
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

    # ✅ FIX: determine business_number from payload and use correct signature
    business_number = _extract_business_number(payload) or os.getenv("META_WA_PHONE_NUMBER_ID")
    if business_number:
        auto_close_expired_surveys(db, business_number)

    msg, sender_raw = _extract_message(payload)
    sender = _normalise_msisdn(sender_raw)

    if not msg or not sender:
        return Response(status_code=200)

    _upsert_client(db, sender)

    # -------------------------------
    # MEDIA
    # -------------------------------
    if handle_media_message(db=db, sender=sender, msg=msg, admin_allowlist=ADMIN_ALLOWLIST):
        return Response(status_code=200)

    # -------------------------------
    # INTERACTIVE (survey answers)
    # -------------------------------
    if msg.get("type") == "interactive":
        reply = msg.get("interactive", {}).get("button_reply")
        if reply:
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
                        button_id=reply.get("id"),
                        tag=reply.get("title"),
                    )
                )
                db.commit()
        return Response(status_code=200)

    # -------------------------------
    # TEXT
    # -------------------------------
    if msg.get("type") == "text":
        text = msg["text"]["body"].strip()
        upper = text.upper()

        # ===============================
        # ADMIN → SEND SURVEY
        # ===============================
        if sender in ADMIN_ALLOWLIST and upper.startswith("SURVEY:"):
            question = text.split(":", 1)[1].strip()
            if not question:
                return Response(status_code=200)

            rows = db.execute(
                sql_text(
                    """
                    SELECT client_number
                    FROM clients
                    WHERE is_paused = false
                      AND last_interaction_at >= now() - interval '24 hours'
                      AND client_number NOT IN :admins
                    """
                ),
                {"admins": tuple(ADMIN_ALLOWLIST)},
            ).fetchall()

            survey = Survey(
                business_number=sender,
                question=question,
                button_set="YES_NO_NOT_SURE",
                status="active",
                ends_at=db.execute(
                    sql_text("SELECT now() + interval '24 hours'")
                ).scalar(),
            )
            db.add(survey)
            db.commit()

            meta = MetaWhatsAppClient(
                MetaWhatsAppSettings(
                    api_version=os.getenv("META_WA_API_VERSION"),
                    access_token=os.getenv("META_WA_ACCESS_TOKEN"),
                    phone_number_id=os.getenv("META_WA_PHONE_NUMBER_ID"),
                )
            )

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

            # ✅ SINGLE admin confirmation
            meta.send_generic_business_update_template(
                to_msisdn=sender,
                blob_text=f"Survey sent to {len(rows)} active clients.",
            )

            return Response(status_code=200)

        # -------------------------------
        # ADMIN COMMANDS (menu, count)
        # -------------------------------
        if handle_admin_command(
            db=db,
            sender_number=sender,
            message_text=text,
            admin_allowlist=ADMIN_ALLOWLIST,
        ):
            return Response(status_code=200)

        handle_client_command(
            db=db,
            sender_number=sender,
            message_text=text,
            msg=msg,
        )

    return Response(status_code=200)
