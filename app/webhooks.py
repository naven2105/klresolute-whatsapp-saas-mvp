"""
File: app/webhooks.py
Path: app/webhooks.py

Project: KLResolute WhatsApp SaaS MVP

Purpose:
Inbound WhatsApp webhook handler.

Admin commands (Tier 1 – LOCKED):
- ADD CLIENT: <number>
- REMOVE CLIENT: <number>
- SEND: <number> <message>   → ALWAYS uses approved template

Standards (MVP):
- ALL outbound admin messages use Meta template
- NO session/free-text messages
- Admin always receives confirmation
"""

import logging
import os
import re

from fastapi import APIRouter, Request, Response, status, Depends
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.db import get_db
from app.models import (
    WhatsAppNumber,
    Client,
    Contact,
    Conversation,
    Message,
    FaqItem,
)
from app.outbound.factory import get_meta_client

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger("webhooks")
logging.basicConfig(level=logging.INFO)

# ------------------------------------------------------------------
# Admin allowlist (MSISDNs)
# ------------------------------------------------------------------
ADMIN_ALLOWLIST = {
    n.strip()
    for n in os.getenv("OUTBOUND_TEST_ALLOWLIST", "").split(",")
    if n.strip()
}


def _normalise_msisdn(raw: str) -> str | None:
    digits = re.sub(r"\D", "", raw or "")
    if not digits:
        return None
    if digits.startswith("0"):
        digits = "27" + digits[1:]
    if digits.startswith("27") and len(digits) >= 11:
        return digits
    return None


def _extract_destination_number(payload: dict) -> str | None:
    try:
        return payload["entry"][0]["changes"][0]["value"]["metadata"]["display_phone_number"]
    except Exception:
        return None


def _extract_sender_number(payload: dict) -> str | None:
    try:
        return payload["entry"][0]["changes"][0]["value"]["messages"][0]["from"]
    except Exception:
        return None


def _extract_message_text(payload: dict) -> str | None:
    try:
        return payload["entry"][0]["changes"][0]["value"]["messages"][0]["text"]["body"]
    except Exception:
        return None


@router.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    # --------------------------------------------------------------
    # Parse payload
    # --------------------------------------------------------------
    try:
        payload = await request.json()
    except Exception:
        return Response(status_code=status.HTTP_200_OK)

    destination_number = _extract_destination_number(payload)
    sender_number = _extract_sender_number(payload)
    message_text = _extract_message_text(payload)

    if not destination_number or not sender_number or not message_text:
        logger.warning("Required message fields missing")
        return Response(status_code=status.HTTP_200_OK)

    logger.info("Destination number: %s", destination_number)
    logger.info("Sender number: %s", sender_number)
    logger.info("Message text: %s", message_text)

    upper_text = message_text.upper().strip()

    # ==============================================================
    # ADMIN COMMANDS
    # ==============================================================

    # ---------------- ADD CLIENT ----------------
    if sender_number in ADMIN_ALLOWLIST and upper_text.startswith("ADD CLIENT:"):
        try:
            _, body = message_text.split(":", 1)
            msisdn = _normalise_msisdn(body.strip())

            if not msisdn:
                logger.warning("ADD CLIENT rejected: invalid number")
                return Response(status_code=status.HTTP_200_OK)

            existing = db.query(Contact).filter(Contact.contact_number == msisdn).one_or_none()
            if existing:
                logger.info("ADD CLIENT duplicate: %s", msisdn)
                get_meta_client().send_generic_business_update_template(
                    to_msisdn=sender_number,
                    blob_text=f"Client {msisdn} already exists.",
                )
                return Response(status_code=status.HTTP_200_OK)

            db.add(Contact(contact_number=msisdn))
            db.commit()

            get_meta_client().send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text=f"Client {msisdn} added successfully.",
            )

            logger.info("ADD CLIENT success: %s", msisdn)

        except Exception:
            db.rollback()
            logger.exception("ADD CLIENT failed")

        return Response(status_code=status.HTTP_200_OK)

    # ---------------- REMOVE CLIENT ----------------
    if sender_number in ADMIN_ALLOWLIST and upper_text.startswith("REMOVE CLIENT:"):
        try:
            _, body = message_text.split(":", 1)
            msisdn = _normalise_msisdn(body.strip())

            if not msisdn:
                logger.warning("REMOVE CLIENT rejected: invalid number")
                return Response(status_code=status.HTTP_200_OK)

            existing = db.query(Contact).filter(Contact.contact_number == msisdn).one_or_none()
            if not existing:
                get_meta_client().send_generic_business_update_template(
                    to_msisdn=sender_number,
                    blob_text=f"Client {msisdn} not found.",
                )
                return Response(status_code=status.HTTP_200_OK)

            db.delete(existing)
            db.commit()

            get_meta_client().send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text=f"Client {msisdn} removed.",
            )

            logger.info("REMOVE CLIENT success: %s", msisdn)

        except IntegrityError:
            db.rollback()
            logger.exception("REMOVE CLIENT blocked by FK constraint")
        except Exception:
            db.rollback()
            logger.exception("REMOVE CLIENT failed")

        return Response(status_code=status.HTTP_200_OK)

    # ---------------- SEND (TEMPLATE ONLY) ----------------
    if sender_number in ADMIN_ALLOWLIST and upper_text.startswith("SEND:"):
        try:
            _, body = message_text.split(":", 1)
            parts = body.strip().split(maxsplit=1)

            if len(parts) < 2:
                get_meta_client().send_generic_business_update_template(
                    to_msisdn=sender_number,
                    blob_text="SEND failed. Format: SEND: <number> <message>",
                )
                return Response(status_code=status.HTTP_200_OK)

            raw_number, text = parts
            msisdn = _normalise_msisdn(raw_number)

            if not msisdn or not text.strip():
                get_meta_client().send_generic_business_update_template(
                    to_msisdn=sender_number,
                    blob_text="SEND failed. Invalid number or message.",
                )
                return Response(status_code=status.HTTP_200_OK)

            get_meta_client().send_generic_business_update_template(
                to_msisdn=msisdn,
                blob_text=text.strip(),
            )

            get_meta_client().send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text=f"Message sent to {msisdn}.",
            )

            logger.info("SEND success to %s", msisdn)

        except Exception:
            logger.exception("SEND failed")
            get_meta_client().send_generic_business_update_template(
                to_msisdn=sender_number,
                blob_text="SEND failed due to system error.",
            )

        return Response(status_code=status.HTTP_200_OK)

    # ==============================================================
    # NON-ADMIN FLOW (unchanged)
    # ==============================================================

    return Response(status_code=status.HTTP_200_OK)
