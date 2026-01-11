"""
File: app/jobs/weekly_whatsapp_report.py

Purpose:
Send weekly WhatsApp engagement summary to admin.
Triggered by Render Cron (Friday 18h00).

Notes:
- Uses existing SQLAlchemy SessionLocal from app/db.py
- Does NOT import request handlers
- Meta client is initialised lazily (no env dependency at import time)
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


def _get_meta_client() -> MetaWhatsAppClient:
    """
    Lazily create Meta client.
    This avoids META_WA_* env dependency during local runs.
    """
    return MetaWhatsAppClient(settings=load_meta_settings())


def send_weekly_whatsapp_report() -> None:
    """
    Build and send the weekly engagement report to admin numbers.
    """

    admin_numbers = _get_admin_allowlist()
    if not admin_numbers:
        return  # nothing to do

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

        meta = _get_meta_client()

        for admin_number in admin_numbers:
            meta.send_session_message(
                to_msisdn=admin_number,
                text=report_text,
            )

    finally:
        db.close()


if __name__ == "__main__":
    send_weekly_whatsapp_report()
