from __future__ import annotations

"""
File: app/jobs/galitos_weekly_whatsapp_report.py

Purpose:
Send weekly WhatsApp engagement summary to FOOD outlet admins only.
Triggered by Render Cron (Friday 18h00).

Rules (LOCKED):
- Single transport gateway only (client_messenger.send_message)
- No direct Meta client usage
- No ADMIN_ALLOWLIST
- Per-business isolation
- GALITOS only (food vertical)
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import text

from app.db import SessionLocal
from app.models import EventLog
from app.messaging.client_messenger import send_message

logger = logging.getLogger("jobs.weekly_report")


def send_weekly_whatsapp_report() -> None:
    db = SessionLocal()

    try:
        logger.info("WEEKLY_REPORT_START")

        end = datetime.utcnow()
        start = end - timedelta(days=7)

        # -------------------------------------------------
        # Fetch all active business numbers
        # -------------------------------------------------
        businesses = (
            db.execute(
                text(
                    """
                    SELECT wn.destination_number,
                           wn.client_id,
                           wn.klresolute_client_id,
                           c.client_name
                    FROM whatsapp_numbers wn
                    JOIN clients c ON c.client_id = wn.client_id
                    WHERE wn.status = 'active'
                    """
                )
            )
            .mappings()
            .all()
        )

        logger.info("WEEKLY_REPORT_BUSINESSES_FOUND | count=%s", len(businesses))

        for b in businesses:

            business_msisdn = b["destination_number"]
            client_uuid = b["client_id"]
            client_name = b["client_name"]

            # -------------------------------------------------
            # Only FOOD vertical (GALITOS)
            # -------------------------------------------------
            if (client_name or "").upper() != "GALITOS":
                logger.info(
                    "WEEKLY_REPORT_SKIP | business=%s | reason=not_food_vertical",
                    business_msisdn,
                )
                continue

            logger.info(
                "WEEKLY_REPORT_PROCESS | business=%s",
                business_msisdn,
            )

            # -------------------------------------------------
            # Engagement counts (last 7 days)
            # -------------------------------------------------
            hours_count = (
                db.query(EventLog)
                .filter(
                    EventLog.event_type == "inbound_keyword",
                    EventLog.event_detail == "keyword_hours",
                    EventLog.event_timestamp >= start,
                )
                .count()
            )

            specials_count = (
                db.query(EventLog)
                .filter(
                    EventLog.event_type == "inbound_keyword",
                    EventLog.event_detail == "keyword_specials",
                    EventLog.event_timestamp >= start,
                )
                .count()
            )

            total_engagement = (
                db.query(EventLog)
                .filter(
                    EventLog.event_type.in_(
                        ["inbound_keyword", "hours_reply_sent", "specials_reply_sent"]
                    ),
                    EventLog.event_timestamp >= start,
                )
                .count()
            )

            report_text = (
                "📊 Weekly WhatsApp Engagement Summary\n\n"
                f"• {hours_count} customers checked store hours\n"
                f"• {specials_count} customers viewed specials/promotions\n"
                f"• {total_engagement} total automated interactions\n\n"
                "This shows reduced call interruptions and clear buying interest."
            )

            # -------------------------------------------------
            # Resolve active admins
            # -------------------------------------------------
            admin_rows = (
                db.execute(
                    text(
                        """
                        SELECT msisdn
                        FROM client_admins
                        WHERE client_code = :code
                          AND is_active = TRUE
                        """
                    ),
                    {"code": client_name},
                )
                .mappings()
                .all()
            )

            if not admin_rows:
                logger.warning(
                    "WEEKLY_REPORT_NO_ADMINS | business=%s",
                    business_msisdn,
                )
                continue

            logger.info(
                "WEEKLY_REPORT_ADMIN_COUNT | business=%s | count=%s",
                business_msisdn,
                len(admin_rows),
            )

            # -------------------------------------------------
            # Send via single transport gateway
            # -------------------------------------------------
            for admin in admin_rows:
                try:
                    send_message(
                        db=db,
                        business_msisdn=business_msisdn,
                        to_number=admin["msisdn"],
                        text=report_text,
                    )

                    logger.info(
                        "WEEKLY_REPORT_SENT | business=%s | admin=%s",
                        business_msisdn,
                        admin["msisdn"],
                    )

                except Exception:
                    logger.exception(
                        "WEEKLY_REPORT_SEND_FAIL | business=%s | admin=%s",
                        business_msisdn,
                        admin["msisdn"],
                    )

        logger.info("WEEKLY_REPORT_COMPLETE")

    except Exception:
        logger.exception("WEEKLY_REPORT_FATAL")

    finally:
        db.close()


if __name__ == "__main__":
    send_weekly_whatsapp_report()
