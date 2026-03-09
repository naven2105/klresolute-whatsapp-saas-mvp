from __future__ import annotations

"""
File: survey_expiry_notifier.py
Path: app/clients/zar/survey/survey_expiry_notifier.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Background notifier that auto-closes expired ZAR surveys.
"""

import logging
import asyncio
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger("zar.survey_expiry_notifier")


async def survey_expiry_notifier(db_factory, interval_seconds: int = 60):

    logger.info(
        "ZAR_EXPIRY_NOTIFIER_START | interval_seconds=%s",
        interval_seconds,
    )

    while True:

        try:

            async with db_factory() as db:

                rows = db.execute(
                    text(
                        """
                        SELECT id
                        FROM r_zar__surveys
                        WHERE status='ACTIVE'
                        AND ends_at < now()
                        """
                    )
                ).fetchall()

                logger.info(
                    "ZAR_EXPIRY_SCAN | expired_found=%s",
                    len(rows),
                )

                for r in rows:

                    try:

                        db.execute(
                            text(
                                """
                                UPDATE r_zar__surveys
                                SET status='CLOSED', closed_at=now()
                                WHERE id=:id
                                """
                            ),
                            {"id": r.id},
                        )

                        db.commit()

                        logger.info(
                            "ZAR_EXPIRY_SURVEY_CLOSED | survey_id=%s",
                            r.id,
                        )

                    except Exception:

                        logger.exception(
                            "ZAR_EXPIRY_CLOSE_FAIL | survey_id=%s",
                            r.id,
                        )

        except Exception:

            logger.exception("ZAR_EXPIRY_LOOP_FAIL")

        await asyncio.sleep(interval_seconds)