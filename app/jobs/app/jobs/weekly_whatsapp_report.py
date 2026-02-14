from __future__ import annotations

"""
File: app/jobs/weekly_whatsapp_report.py
Path: app/jobs/weekly_whatsapp_report.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Compatibility wrapper for Render Cron.

Why this exists:
- Render Cron is configured to run: `python -m app.jobs.weekly_whatsapp_report`
- The current implementation lives in: `app/jobs/galitos_weekly_whatsapp_report.py`
- This wrapper preserves the cron command and delegates to the real job.

Rules:
- No business logic here
- Delegate only
"""

import logging

from app.jobs.galitos_weekly_whatsapp_report import send_weekly_whatsapp_report

logger = logging.getLogger("jobs.weekly_whatsapp_report")


def main() -> None:
    logger.info("WEEKLY_WHATSAPP_REPORT_WRAPPER_START")
    send_weekly_whatsapp_report()
    logger.info("WEEKLY_WHATSAPP_REPORT_WRAPPER_COMPLETE")


if __name__ == "__main__":
    main()
