from __future__ import annotations

"""
File: app/modules/broadcast/repo.py
Path: app/modules/broadcast/repo.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Persistence layer for Broadcast module.

STATUS:
⚠️ ARCHIVED / LEGACY

Context:
- The Broadcast feature has been retired.
- The `broadcasts` table has been archived/removed.
- Customer outbound communication is now handled via the
  general customer messaging infrastructure.
- This repository remains only for historical reference
  and backward traceability.

Responsibilities (HISTORICAL):
- Store broadcast intent (text / image)
- Resolve recipient MSISDNs

NO outbound messaging.
NO permission logic.
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger("module.broadcast.repo")


# -------------------------------------------------
# Persist broadcasts (ARCHIVED)
# -------------------------------------------------

def save_text_broadcast(
    *,
    db: Session,
    business_msisdn: str,
    sender: str,
    text: str,
) -> int:
    """
    ARCHIVED / LEGACY

    Persist a text broadcast.

    NOTE:
    - The `broadcasts` table is no longer authoritative.
    - This function is retained only to avoid breaking
      legacy call paths during migration.
    """

    row = db.execute(
        text(
            """
            INSERT INTO broadcasts (
                business_msisdn,
                sender_msisdn,
                type,
                body
            )
            VALUES (
                :business,
                :sender,
                'TEXT',
                :body
            )
            RETURNING id
            """
        ),
        {
            "business": business_msisdn,
            "sender": sender,
            "body": text,
        },
    ).first()

    db.commit()

    broadcast_id = row.id
    logger.info("BROADCAST_TEXT_SAVED (ARCHIVED) | id=%s", broadcast_id)
    return broadcast_id


def save_image_broadcast(
    *,
    db: Session,
    business_msisdn: str,
    sender: str,
    media_id: str,
    caption: str | None,
) -> int:
    """
    ARCHIVED / LEGACY

    Persist an image broadcast.
    """

    row = db.execute(
        text(
            """
            INSERT INTO broadcasts (
                business_msisdn,
                sender_msisdn,
                type,
                media_id,
                body
            )
            VALUES (
                :business,
                :sender,
                'IMAGE',
                :media_id,
                :caption
            )
            RETURNING id
            """
        ),
        {
            "business": business_msisdn,
            "sender": sender,
            "media_id": media_id,
            "caption": caption,
        },
    ).first()

    db.commit()

    broadcast_id = row.id
    logger.info("BROADCAST_IMAGE_SAVED (ARCHIVED) | id=%s", broadcast_id)
    return broadcast_id


# -------------------------------------------------
# Recipients (ARCHIVED)
# -------------------------------------------------

def get_broadcast_recipients(
    db: Session,
    business_msisdn: str,
) -> list[str]:
    """
    ARCHIVED / LEGACY

    Resolve all opted-in recipients for a business.
    """

    rows = (
        db.execute(
            text(
                """
                SELECT contact_number
                FROM contacts
                WHERE business_msisdn = :business
                  AND is_active = TRUE
                """
            ),
            {"business": business_msisdn},
        )
        .mappings()
        .all()
    )

    recipients = [r["contact_number"] for r in rows]

    logger.info(
        "BROADCAST_RECIPIENTS (ARCHIVED) | business=%s | count=%s",
        business_msisdn,
        len(recipients),
    )

    return recipients
