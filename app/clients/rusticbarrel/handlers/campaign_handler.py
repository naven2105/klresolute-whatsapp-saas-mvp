# ==================================================
# File: campaign_handler.py
# Path: app/clients/rusticbarrel/handlers/campaign_handler.py
# Project: KLResolute WhatsApp SaaS MVP
#
# Sprint 24 – Admin Menu Isolation
#
# Purpose:
# Handles Rustic Barrel admin campaign flow:
# - Pending confirmation state (in-memory)
# - Lazy expiry (60 seconds)
# - Text campaign trigger
# - Image campaign trigger
# - YES / NO confirmation
# - Broadcast execution
# - DB insert (campaign + logs)
#
# Update (Sprint 24):
# - Admin menu removed from campaign handler
# - Unknown admin commands must fall back to admin_menu_service
#
# Isolation:
# - rustic barrel only
# - No dispatcher changes
# - No lifecycle states
# ==================================================

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.messaging.client_messenger import send_message

logger = logging.getLogger("rusticbarrel.campaign_handler")

pending_campaigns: dict[str, dict] = {}
EXPIRY_SECONDS = 60


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
    msg_lower = msg.lower()

    pending = pending_campaigns.get(sender_msisdn)

    # --------------------------------------------------
    # Pending confirmation state
    # --------------------------------------------------
    if pending:

        created_at = pending["created_at"]

        if now - created_at > timedelta(seconds=EXPIRY_SECONDS):

            send_message(
                db=db,
                business_msisdn=business_msisdn,
                to_number=sender_msisdn,
                text="Campaign request expired. No message was sent.",
            )

            del pending_campaigns[sender_msisdn]
            return True

        if msg_lower == "yes":
            _execute_broadcast(
                db=db,
                business_msisdn=business_msisdn,
                admin_msisdn=sender_msisdn,
                pending=pending,
            )
            del pending_campaigns[sender_msisdn]
            return True

        if msg_lower == "no":
            send_message(
                db=db,
                business_msisdn=business_msisdn,
                to_number=sender_msisdn,
                text="Campaign cancelled.",
            )
            del pending_campaigns[sender_msisdn]
            return True

        # Invalid confirmation response
        send_message(
            db=db,
            business_msisdn=business_msisdn,
            to_number=sender_msisdn,
            text="Please reply YES to send or NO to cancel.",
        )
        return True

    # --------------------------------------------------
    # Text campaign trigger
    # --------------------------------------------------
    if message_type == "text" and msg_lower.startswith("announcement:"):

        campaign_text = msg.split(":", 1)[1].strip()

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

    # --------------------------------------------------
    # Image campaign trigger
    # --------------------------------------------------
    if message_type == "image":

        return _create_pending(
            db=db,
            business_msisdn=business_msisdn,
            admin_msisdn=sender_msisdn,
            campaign_type="image",
            message=msg if msg else None,
            image_url=media_url,
        )

    # --------------------------------------------------
    # Not a campaign command
    # --------------------------------------------------
    return False


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
            FROM r_rusticbarrel__customers
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
            FROM r_rusticbarrel__customers
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
            INSERT INTO r_rusticbarrel__campaigns
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
                    "📢 Rustic Barrel Announcement\n\n"
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
                        "📢 Rustic Barrel Announcement\n\n"
                        f"{message}"
                    )
                else:
                    formatted_caption = None

                send_message(
                    db=db,
                    business_msisdn=business_msisdn,
                    to_number=row.phone,
                    image_id=image_url,
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
                INSERT INTO r_rusticbarrel__broadcast_logs
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
            UPDATE r_rusticbarrel__campaigns
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