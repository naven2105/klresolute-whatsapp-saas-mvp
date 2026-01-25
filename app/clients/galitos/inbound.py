from __future__ import annotations

"""
File: app/clients/galitos/inbound.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Inbound dispatcher for Galitos WhatsApp number.

RULES (LOCKED):
- conversation_state is the ONLY source of truth
- messages table is NEVER used for flow decisions
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.outbound.factory import get_meta_client

logger = logging.getLogger("clients.galitos")
meta = get_meta_client()

GALITOS_BUSINESS_MSISDN = "27735534607"


# -------------------------------------------------
# State helpers
# -------------------------------------------------

def _get_active_order(db: Session, sender: str):
    return db.execute(
        text(
            """
            SELECT *
            FROM conversation_state
            WHERE sender_msisdn = :sender
              AND active = TRUE
            LIMIT 1
            """
        ),
        {"sender": sender},
    ).mappings().first()


# -------------------------------------------------
# Inbound handler
# -------------------------------------------------

def handle_inbound(
    *,
    db: Session,
    business_msisdn: str | None,
    sender: str,
    msg: dict,
) -> bool:
    if business_msisdn != GALITOS_BUSINESS_MSISDN:
        return False

    if msg.get("type") != "text":
        return False

    text_body = msg["text"]["body"].strip()
    upper = text_body.upper()

    active = _get_active_order(db, sender)

    # ----------------------------------
    # Order confirmation (YES / NO)
    # ----------------------------------
    if active and active["flavour"] is not None and active["order_pending"]:

        if upper == "YES":
            db.execute(
                text(
                    """
                    UPDATE conversation_state
                    SET
                        order_pending = FALSE,
                        active = FALSE,
                        completed_at = now()
                    WHERE id = :id
                    """
                ),
                {"id": active["id"]},
            )
            db.commit()

            meta.send_session_message(
                to_msisdn=sender,
                text=(
                    "✅ Order confirmed.\n\n"
                    "Thank you for choosing Galitos 🍗"
                ),
            )
            logger.info("GALITOS_ORDER_CONFIRMED | sender=%s", sender)
            return True

        if upper == "NO":
            db.execute(
                text(
                    """
                    UPDATE conversation_state
                    SET active = FALSE,
                        completed_at = now()
                    WHERE id = :id
                    """
                ),
                {"id": active["id"]},
            )
            db.commit()

            meta.send_session_message(
                to_msisdn=sender,
                text="❌ Order cancelled.",
            )
            logger.info("GALITOS_ORDER_CANCELLED | sender=%s", sender)
            return True

        # Awaiting YES/NO → ignore everything else
        meta.send_session_message(
            to_msisdn=sender,
            text="Please reply YES to confirm or NO to cancel.",
        )
        return True

    # ----------------------------------
    # Let customer_commands handle rest
    # ----------------------------------
    return False
