from __future__ import annotations

"""
File: survey_expiry_notifier.py
Path: app/clients/rusticbarrel/survey/survey_expiry_notifier.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Background notifier that auto-closes expired rusticbarrel surveys.

Rules:
- Tenant isolated
- Uses r_galitos__surveys
- No cross-tenant logic
"""

import asyncio
import logging
import os

from sqlalchemy import text

from app.db import SessionLocal

logger = logging.getLogger("rusticbarrel.survey_expiry_notifier")


def _get_interval_seconds() -> int:
    raw = (os.getenv("SURVEY_EXPIRY_NOTIFIER_INTERVAL_SECONDS", "300") or "").strip()
    try:
        return max(30, int(raw))
    except Exception:
        return 300


async def _run_forever() -> None:

    interval = _get_interval_seconds()

    logger.info(
        "GALITOS_EXPIRY_NOTIFIER_START | interval_seconds=%s",
        interval,
    )

    while True:

        try:

            db = SessionLocal()

            rows = (
                db.execute(
                    text(
                        """
                        SELECT id
                        FROM r_galitos__surveys
                        WHERE status = 'ACTIVE'
                          AND ends_at <= now()
                        ORDER BY ends_at ASC
                        LIMIT 20
                        """
                    )
                )
                .mappings()
                .all()
            )

            logger.info("GALITOS_EXPIRY_SCAN | expired_found=%s", len(rows))

            for r in rows:

                survey_id = r.get("id")

                try:

                    db.execute(
                        text(
                            """
                            UPDATE r_galitos__surveys
                            SET status = 'CLOSED',
                                closed_at = now()
                            WHERE id = :survey_id
                            """
                        ),
                        {"survey_id": survey_id},
                    )

                    db.commit()

                    logger.info(
                        "GALITOS_EXPIRY_SURVEY_CLOSED | survey_id=%s",
                        survey_id,
                    )

                except Exception:

                    db.rollback()

                    logger.exception(
                        "GALITOS_EXPIRY_CLOSE_FAIL | survey_id=%s",
                        survey_id,
                    )

        except Exception:
            logger.exception("GALITOS_EXPIRY_LOOP_FAIL")

        finally:
            try:
                db.close()
            except Exception:
                pass

        await asyncio.sleep(interval)


def start_survey_expiry_notifier() -> None:

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        logger.warning("GALITOS_EXPIRY_NO_LOOP")
        return

    logger.info("GALITOS_EXPIRY_NOTIFIER_SPAWN")

    asyncio.create_task(_run_forever())