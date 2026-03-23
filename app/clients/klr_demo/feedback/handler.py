from __future__ import annotations

"""
File: app/clients/klr_demo/feedback/handler.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
klr_demo-specific feedback handler (tenant-isolated).

Rules:
- Trigger: "feedback:"
- Store in r_klr_demo__feedback
- Forward to admins (role='admin')
- Acknowledge customer
- No shared tables
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.messaging.client_messenger import send_message
from app.messaging.template_registry import PLATFORM_ADMIN_FEEDBACK

logger = logging.getLogger("klr_demo.feedback")


def handle_feedback_message(
    *,
    db: Session,
    sender_number: str,
    message_text: str | None,
    media_id: str | None,
    media_type: str | None,
    business_msisdn: str,
) -> bool:

    if not message_text and not media_id:
        return False

    msg = (message_text or "").strip()

    if not msg.lower().startswith("feedback:"):
        return False

    feedback_body = msg[len("feedback:") :].strip() if message_text else None

    if not feedback_body and not media_id:
        send_message(
            db=db,
            business_msisdn=business_msisdn,
            to_number=sender_number,
            text="Please provide feedback after 'feedback:'",
        )
        return True

    try:
        # --------------------------------------------------
        # Store feedback (tenant table)
        # --------------------------------------------------
        db.execute(
            text(
                """
                INSERT INTO r_klr_demo__feedback
                (customer_msisdn, message_text, media_id, media_type)
                VALUES (:customer_msisdn, :message_text, :media_id, :media_type)
                """
            ),
            {
                "customer_msisdn": sender_number,
                "message_text": feedback_body,
                "media_id": media_id,
                "media_type": media_type,
            },
        )
        db.commit()

    except SQLAlchemyError:
        db.rollback()
        logger.exception("KLR_FEEDBACK_STORE_FAIL")
        return True

    # --------------------------------------------------
    # Fetch admins
    # --------------------------------------------------
    rows = db.execute(
        text(
            """
            SELECT msisdn
            FROM r_klr_demo__staff
            WHERE role = 'admin'
            """
        )
    ).fetchall()

    clean_message = (feedback_body or "Media received").replace("\n", " ").strip()

    alert_text = (
        f"New feedback received | "
        f"From: {sender_number} | "
        f"Message: {clean_message}"
    )

    for row in rows:
        try:
            send_message(
                db=db,
                business_msisdn=business_msisdn,
                to_number=row.msisdn,
                template_name=PLATFORM_ADMIN_FEEDBACK,
                template_params=[alert_text],
            )
        except Exception:
            logger.exception("KLR_FEEDBACK_ADMIN_SEND_FAIL")

    # --------------------------------------------------
    # Customer acknowledgement (session message)
    # --------------------------------------------------
    send_message(
        db=db,
        business_msisdn=business_msisdn,
        to_number=sender_number,
        text="🙏 Thank you for your feedback. It has been sent to management.",
    )

    return True
