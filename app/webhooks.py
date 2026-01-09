"""
File: app/webhooks.py
Project: KLResolute WhatsApp SaaS MVP
"""

import logging
import os
import re
from datetime import timedelta

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

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger("webhooks")
logging.basicConfig(level=logging.INFO)

ADMIN_ALLOWLIST = {
    n.strip()
    for n in os.getenv("OUTBOUND_TEST_ALLOWLIST", "").split(",")
    if n.strip()
}

SURVEY_AUTO_CLOSE_HOURS = int(os.getenv("SURVEY_AUTO_CLOSE_HOURS", "24"))


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


def _auto_close_expired_surveys(db: Session) -> None:
    """
    Opportunistically close expired surveys.
    Safe to call on every webhook.
    """
    db.execute(
        sql_text(
            """
            UPDATE surveys
            SET status = 'closed',
                ended_at = now()
            WHERE status = 'active'
              AND started_at < now() - (:hours || ' hours')::interval
            """
        ),
        {"hours": SURVEY_AUTO_CLOSE_HOURS},
    )
    db.commit()


@router.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    logger.info("WhatsApp webhook received")

    # ✅ auto-close first (cheap + safe)
    _auto_close_expired_surveys(db)

    try:
        payload = await request.json()
    except Exception:
        return Response(status_code=200)

    msg, sender_raw = _extract_message(payload)
    sender = _normalise_msisdn(sender_raw)

    if not msg or not sender:
        return Response(status_code=200)

    _upsert_client(db, sender)

    if handle_media_message(db=db, sender=sender, msg=msg, admin_allowlist=ADMIN_ALLOWLIST):
        return Response(status_code=200)

    # -----------------------------------
    # Interactive button replies
    # -----------------------------------
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

    # -----------------------------------
    # TEXT
    # -----------------------------------
    if msg.get("type") == "text":
        text = msg["text"]["body"].strip()
        upper = text.upper()

        # =====================================
        # ADMIN: SEND SURVEY
        # =====================================
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
                      AND client_number NOT IN :admin_numbers
                    """
                ),
                {"admin_numbers": tuple(ADMIN_ALLOWLIST)},
            ).fetchall()

            survey = Survey(
                question=question,
                status="active",
                sent_to_count=len(rows),
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

            return Response(status_code=200)

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
