"""
File: app/jobs/weekly_whatsapp_report.py

Purpose:
Send weekly WhatsApp engagement summary to admin.
Triggered by Render Cron (Friday 18h00).

Local behaviour:
- If META envs are missing, report is BUILT but NOT SENT
"""

import os
from datetime import datetime, timedelta, timezone

from app.db import SessionLocal
from app.models import EventLog
from app.outbound.meta import MetaWhatsAppClient
from app.outbound.settings import load_meta_settings


def _get_admin_allowlist() -> list[str]:
    raw = os.getenv("OUTBOUND_TEST_ALLOWLIST", "")
    return [n.strip() for n in raw.split(",") if n.strip()]


def _meta_envs_present() -> bool:
    return bool(os.getenv("META_WA_ACCESS_TOKEN"))


def send_weekly_whatsapp_report() -> None:
    admin_numbers = _get_admin_allowlist()
    if not admin_numbers:
        print("No admin numbers configured – skipping report")
        return

    db = SessionLocal()
    try:
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)

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
                EventLog.event_type.in_(["inbound_keyword", "inbound_message"]),
                EventLog.event_timestamp >= start,
            )
            .count()
        )

        report_text = (
            "📊 Weekly WhatsApp Engagement Summary\n\n"
            f"• {hours_count} customers checked store hours\n"
            f"• {specials_count} customers requested specials\n"
            f"• {total_engagement} total customer interactions\n\n"
            "This reduced phone interruptions and highlighted customer demand."
        )

        # ---- LOCAL GUARD ----
        if not _meta_envs_present():
            print("META envs not present – report generated but not sent")
            print(report_text)
            return

        # ---- SEND (Render only) ----
        meta = MetaWhatsAppClient(settings=load_meta_settings())

        for admin_number in admin_numbers:
            meta.send_session_message(
                to_msisdn=admin_number,
                text=report_text,
            )

    finally:
        db.close()


if __name__ == "__main__":
    send_weekly_whatsapp_report()
