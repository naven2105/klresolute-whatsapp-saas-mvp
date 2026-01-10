"""
File: app/jobs/weekly_whatsapp_report.py

Purpose:
Send weekly WhatsApp engagement summary to admin.
Triggered by scheduler (Render cron / task).
"""

from datetime import datetime, timedelta

from app.outbound.meta import MetaWhatsAppClient
from app.outbound.settings import load_meta_settings
from app.models import EventLog
from app.config import ADMIN_ALLOWLIST  # already exists in your project


_meta_client = MetaWhatsAppClient(settings=load_meta_settings())


def send_weekly_whatsapp_report(db) -> None:
    """
    Builds and sends the weekly engagement report to admins only.
    """

    end = datetime.utcnow()
    start = end - timedelta(days=7)

    # 1️⃣ Hours queries (call replacement)
    hours_count = (
        db.query(EventLog)
        .filter(
            EventLog.event_type == "inbound_keyword",
            EventLog.event_detail == "keyword_hours",
            EventLog.event_timestamp >= start,
        )
        .count()
    )

    # 2️⃣ Specials interest (sales signal)
    specials_count = (
        db.query(EventLog)
        .filter(
            EventLog.event_type == "inbound_keyword",
            EventLog.event_detail == "keyword_specials",
            EventLog.event_timestamp >= start,
        )
        .count()
    )

    # 3️⃣ Total engagement
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
        "This helped reduce phone interruptions and highlight customer interest."
    )

    for admin_number in ADMIN_ALLOWLIST:
        _meta_client.send_session_message(
            to_msisdn=admin_number,
            text=report_text,
        )
