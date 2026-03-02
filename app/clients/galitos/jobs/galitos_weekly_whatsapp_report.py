from __future__ import annotations

"""
File: app/clients/galitos/jobs/weekly_whatsapp_report.py
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import text

from app.db import SessionLocal
from app.models import EventLog
from app.messaging.client_messenger import send_message

logger = logging.getLogger("jobs.galitos_weekly_report")

GALITOS_CLIENT_UUID = "906a5084-1add-4b7a-bda0-90b462c9b8a9"


def send_weekly_whatsapp_report() -> None:
    db = SessionLocal()

    try:
        logger.info("GALITOS_WEEKLY_REPORT_START")

        end = datetime.utcnow()
        start = end - timedelta(days=7)

        businesses = (
            db.execute(
                text(
                    """
                    SELECT wn.destination_number,
                           wn.client_id
                    FROM whatsapp_numbers wn
                    WHERE wn.status = 'active'
                      AND wn.client_id = :client_id
                    """
                ),
                {"client_id": GALITOS_CLIENT_UUID},
            )
            .mappings()
            .all()
        )

        for b in businesses:

            business_msisdn = b["destination_number"]
            client_uuid = b["client_id"]

            hours_count = (
                db.query(EventLog)
                .filter(
                    EventLog.client_id == client_uuid,
                    EventLog.event_type == "inbound_keyword",
                    EventLog.event_detail == "keyword_hours",
                    EventLog.event_timestamp >= start,
                )
                .count()
            )

            announcements_count = (
                db.query(EventLog)
                .filter(
                    EventLog.client_id == client_uuid,
                    EventLog.event_type == "inbound_keyword",
                    EventLog.event_detail == "keyword_announcements",
                    EventLog.event_timestamp >= start,
                )
                .count()
            )

            total_engagement = (
                db.query(EventLog)
                .filter(
                    EventLog.client_id == client_uuid,
                    EventLog.event_type.in_(
                        [
                            "inbound_keyword",
                            "hours_reply_sent",
                            "announcements_reply_sent",
                        ]
                    ),
                    EventLog.event_timestamp >= start,
                )
                .count()
            )

            report_text = (
                "📊 Weekly WhatsApp Engagement Summary\n\n"
                f"• {hours_count} customers checked store hours\n"
                f"• {announcements_count} customers viewed announcements\n"
                f"• {total_engagement} total automated interactions\n\n"
                "This shows reduced call interruptions and clear buying interest."
            )

            admin_rows = (
                db.execute(
                    text(
                        """
                        SELECT ca.msisdn
                        FROM client_admins ca
                        JOIN klresolute_client kc
                          ON UPPER(kc.name) = ca.client_code
                        JOIN whatsapp_numbers wn
                          ON wn.destination_number = kc.whatsapp_number
                        WHERE wn.client_id = :client_id
                          AND ca.is_active = TRUE
                        """
                    ),
                    {"client_id": client_uuid},
                )
                .mappings()
                .all()
            )

            for admin in admin_rows:
                send_message(
                    db=db,
                    business_msisdn=business_msisdn,
                    to_number=admin["msisdn"],
                    text=report_text,
                )

        logger.info("GALITOS_WEEKLY_REPORT_COMPLETE")

    except Exception:
        logger.exception("GALITOS_WEEKLY_REPORT_FATAL")

    finally:
        db.close()


if __name__ == "__main__":
    send_weekly_whatsapp_report()