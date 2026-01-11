"""
File: app/jobs/weekly_whatsapp_report.py

Purpose:
Send weekly WhatsApp engagement summary to admin.
Triggered by Render Cron (Friday 18h00).

Notes:
- Uses SQLAlchemy SessionLocal
- Safe to run without META envs (prints report instead)
"""

from datetime import datetime, timedelta

from app.db import SessionLocal
from app.models import EventLog
from app.outbound.meta import MetaWhatsAppClient
from app.outbound.settings import load_meta_settings
from app.handlers.client_commands import ADMIN_ALLOWLIST


def _get_meta_client():
    try:
        return MetaWhatsAppClient(settings=load_meta_settings())
    except RuntimeError:
        return None


def send_weekly_whatsapp_report() -> None:
    db = SessionLocal()
    try:
        end = datetime.utcnow()
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

        meta = _get_meta_client()

        if not meta:
            print("META envs not present – report generated but not sent")
            print(report_text)
            return

        for admin_number in ADMIN_ALLOWLIST:
            meta.send_session_message(
                to_msisdn=admin_number,
                text=report_text,
            )

    finally:
        db.close()


if __name__ == "__main__":
    send_weekly_whatsapp_report()
"""
File: app/jobs/weekly_whatsapp_report.py

Purpose:
Send weekly WhatsApp engagement summary to admin.
Triggered by Render Cron (Friday 18h00).

Notes:
- Uses SQLAlchemy SessionLocal
- Safe to run without META envs (prints report instead)
"""

from datetime import datetime, timedelta

from app.db import SessionLocal
from app.models import EventLog
from app.outbound.meta import MetaWhatsAppClient
from app.outbound.settings import load_meta_settings
from app.handlers.client_commands import ADMIN_ALLOWLIST


def _get_meta_client():
    try:
        return MetaWhatsAppClient(settings=load_meta_settings())
    except RuntimeError:
        return None


def send_weekly_whatsapp_report() -> None:
    db = SessionLocal()
    try:
        end = datetime.utcnow()
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

        meta = _get_meta_client()

        if not meta:
            print("META envs not present – report generated but not sent")
            print(report_text)
            return

        for admin_number in ADMIN_ALLOWLIST:
            meta.send_session_message(
                to_msisdn=admin_number,
                text=report_text,
            )

    finally:
        db.close()


if __name__ == "__main__":
    send_weekly_whatsapp_report()
