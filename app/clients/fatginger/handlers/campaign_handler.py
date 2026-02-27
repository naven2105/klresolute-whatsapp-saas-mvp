# ==================================================
# File: campaign_handler.py
# Path: app/clients/fatginger/handlers/campaign_handler.py
# Project: KLResolute WhatsApp SaaS MVP
#
# Sprint 16 – WhatsApp-Native Campaign Engine
#
# Purpose:
# Handles FatGinger admin campaign flow:
# - Pending confirmation state (in-memory)
# - Lazy expiry (60 seconds)
# - Text campaign trigger
# - Image campaign trigger
# - YES / NO confirmation
# - Broadcast execution
# - DB insert (campaign + logs)
#
# Isolation:
# - FatGinger only
# - No dispatcher changes
# - No lifecycle states
# ==================================================

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.messaging.client_messenger import send_message

logger = logging.getLogger("fatginger.campaign_handler")

# --------------------------------------------------
# In-Memory Pending Store (Per Admin)
# --------------------------------------------------

pending_campaigns: dict[str, dict] = {}

EXPIRY_SECONDS = 60


# --------------------------------------------------
# Public Entry
# --------------------------------------------------

def handle_admin_message(
    db: Session,
    sender_msisdn: str,
    business_msisdn: str,
    message_text: str | None,
    message_type: str,
    media_url: str | None,
) -> bool:

    now = datetime.utcnow()
    msg = (message_text or "").strip()

    # --------------------------------------------------
    # 1️⃣ Check Pending
    # --------------------------------------------------
    pending = pending_campaigns.get(sender_msisdn)

    if pending:

        created_at = pending["created_at"]

        # Expired?
        if now - created_at > timedelta(seconds=EXPIRY_SECONDS):

            send_message(
                db=db,
                business_msisdn=business_msisdn,
                to_number=sender_msisdn,
                text="Campaign request expired. No message was sent.",
            )

            del pending_campaigns[sender_msisdn]
            pending = None

        else:
            # Active confirmation
            if msg.lower() == "yes":
                _execute_broadcast(
                    db=db,
                    business_msisdn=business_msisdn,
                    admin_msisdn=sender_msisdn,
                    pending=pending,
                )
                del pending_campaigns[sender_msisdn]
                return True

            if msg.lower() == "no":
                send_message(
                    db=db,
                    business_msisdn=business_msisdn,
                    to_number=sender_msisdn,
                    text="Campaign cancelled.",
                )
                del pending_campaigns[sender_msisdn]
                return True

            # Unknown while pending
            send_message(
                db=db,
                business_msisdn=business_msisdn,
                to_number=sender_msisdn,
                text=_admin_menu(),
            )
            del pending_campaigns[sender_msisdn]
            return True

    # --------------------------------------------------
    # 2️⃣ New Campaign Trigger
    # --------------------------------------------------

    # Text trigger: announcement:
    if message_type == "text" and msg.lower().startswith("announcement:"):

        campaign_text = msg[len("announcement:") :].strip()

        if not campaign_text:
            send_message(
                db=db,
                business_msisdn=business_msisdn,
                to_number=sender_msisdn,
                text="Campaign text cannot be empty.",
            )
            return True

        return _create_pending(
            db=db,
            business_msisdn=business_msisdn,
            admin_msisdn=sender_msisdn,
            campaign_type="text",
            message=campaign_text,
            image_url=None,
        )

    # Image trigger
    if message_type == "image":

        return _create_pending(
            db=db,
            business_msisdn=business_msisdn,
            admin_msisdn=sender_msisdn,
            campaign_type="image",
            message=msg if msg else None,
            image_url=media_url,
        )

    # Explicit admin menu
    if message_type == "text" and msg.lower() == "admin":
        send_message(
            db=db,
            business_msisdn=business_msisdn,
            to_number=sender_msisdn,
            text=_admin_menu(),
        )
        return True

    # Fallback
    send_message(
        db=db,
        business_msisdn=business_msisdn,
        to_number=sender_msisdn,
        text=_admin_menu(),
    )
    return True


# --------------------------------------------------
# Pending Creation
# --------------------------------------------------

def _create_pending(
    db: Session,
    business_msisdn: str,
    admin_msisdn: str,
    campaign_type: str,
    message: str | None,
    image_url: str | None,
) -> bool:

    result = db.execute(
        text(
            """
            SELECT phone
            FROM r_fg__customers
            WHERE marketing_opt_in = TRUE
            """
        )
    )

    recipients = result.fetchall()
    count = len(recipients)

    if count == 0:
        send_message(
            db=db,
            business_msisdn=business_msisdn,
            to_number=admin_msisdn,
            text="No opted-in customers. Campaign not created.",
        )
        return True

    if admin_msisdn in pending_campaigns:
        del pending_campaigns[admin_msisdn]
        send_message(
            db=db,
            business_msisdn=business_msisdn,
            to_number=admin_msisdn,
            text="Previous pending campaign cancelled.",
        )

    pending_campaigns[admin_msisdn] = {
        "type": campaign_type,
        "message": message,
        "image_url": image_url,
        "recipient_count": count,
        "created_at": datetime.utcnow(),
    }

    confirmation = (
        f"You are about to send this campaign to {count} customers.\n\n"
    )

    if campaign_type == "text":
        confirmation += f"\"{message}\"\n\n"
    else:
        if message:
            confirmation += f"Image caption:\n\"{message}\"\n\n"
        else:
            confirmation += "Image with no caption.\n\n"

    confirmation += (
        "Reply YES to send.\n"
        "Reply NO to cancel.\n"
        "This request expires in 1 minute."
    )

    send_message(
        db=db,
        business_msisdn=business_msisdn,
        to_number=admin_msisdn,
        text=confirmation,
    )

    return True


# --------------------------------------------------
# Broadcast Execution
# --------------------------------------------------

def _execute_broadcast(
    db: Session,
    business_msisdn: str,
    admin_msisdn: str,
    pending: dict,
) -> None:

    campaign_type = pending["type"]
    message = pending["message"]
    image_url = pending["image_url"]

    result = db.execute(
        text(
            """
            SELECT phone
            FROM r_fg__customers
            WHERE marketing_opt_in = TRUE
            """
        )
    )

    recipients = result.fetchall()

    sent_count = 0
    failed_count = 0

    campaign_id = db.execute(
        text(
            """
            INSERT INTO r_fg__campaigns
            (type, message, image_url, total_recipients, sent_count, failed_count)
            VALUES (:type, :message, :image_url, :total, 0, 0)
            RETURNING id
            """
        ),
        {
            "type": campaign_type,
            "message": message,
            "image_url": image_url,
            "total": len(recipients),
        },
    ).scalar()

    db.commit()

    for row in recipients:
        try:
            if campaign_type == "text":
                formatted_message = (
                    "📢 Fat Ginger Announcement\n\n"
                    f"{message}"
                )

                send_message(
                    db=db,
                    business_msisdn=business_msisdn,
                    to_number=row.phone,
                    text=formatted_message,
                )
            else:
                if message:
                    formatted_caption = (
                        "📢 Fat Ginger Announcement\n\n"
                        f"{message}"
                    )
                else:
                    formatted_caption = None

                send_message(
                    db=db,
                    business_msisdn=business_msisdn,
                    to_number=row.phone,
                    image_url=image_url,
                    caption=formatted_caption,
                )

            sent_count += 1
            status = "SENT"

        except Exception:
            failed_count += 1
            status = "FAILED"

        db.execute(
            text(
                """
                INSERT INTO r_fg__broadcast_logs
                (campaign_id, customer_phone, delivery_status)
                VALUES (:cid, :phone, :status)
                """
            ),
            {
                "cid": campaign_id,
                "phone": row.phone,
                "status": status,
            },
        )

    db.execute(
        text(
            """
            UPDATE r_fg__campaigns
            SET sent_count = :sent,
                failed_count = :failed
            WHERE id = :cid
            """
        ),
        {
            "sent": sent_count,
            "failed": failed_count,
            "cid": campaign_id,
        },
    )

    db.commit()

    summary = (
        "Campaign sent.\n\n"
        f"Total: {len(recipients)}\n"
        f"Sent: {sent_count}\n"
        f"Failed: {failed_count}"
    )

    send_message(
        db=db,
        business_msisdn=business_msisdn,
        to_number=admin_msisdn,
        text=summary,
    )


# --------------------------------------------------
# Admin Menu
# --------------------------------------------------

def _admin_menu() -> str:
    return (
        "Admin Menu:\n\n"
        "• announcement: <text> – Send text campaign\n"
        "• Send image with optional caption – Prepare image campaign"
    )