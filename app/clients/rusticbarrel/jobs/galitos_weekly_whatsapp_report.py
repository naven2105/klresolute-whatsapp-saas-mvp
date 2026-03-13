"""
File: rusticbarrel_weekly_whatsapp_report.py
Path: app/clients/rusticbarrel/jobs/rusticbarrel_weekly_whatsapp_report.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Weekly Rustic barrel WhatsApp reporting cron job.

Currently a safe placeholder so the Render cron job
can execute without failure.

Future:
Will generate weekly operational metrics and send
report to rusticbarrel admin.
"""

from __future__ import annotations

import logging
from datetime import datetime


logging.basicConfig(level=logging.INFO)


def run() -> None:
    """
    Entry point for weekly report cron job.
    """

    logging.info("rusticbarrel weekly WhatsApp report job started")
    logging.info("Timestamp: %s", datetime.utcnow().isoformat())

    # TODO:
    # future weekly metrics logic will go here

    logging.info("rusticbarrel weekly WhatsApp report job completed")


if __name__ == "__main__":
    run()