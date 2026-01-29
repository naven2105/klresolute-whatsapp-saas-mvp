from __future__ import annotations

"""
File: app/modules/survey/survey_expiry_notifier.py
Path: app/modules/survey/survey_expiry_notifier.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Background notifier that auto-closes expired ACTIVE surveys and notifies admins.

Why:
Without this job, surveys only auto-close when an inbound message arrives.
This job closes surveys even when nobody messages the bot.

Rules:
- Uses existing DB + survey helpers.
- Uses Meta template (generic_business_update) for admin notifications.
- Heavy logging for Render debugging.

Env flags:
- SURVEY_EXPIRY_NOTIFIER_ENABLED: "1" (default) or "0"
- SURVEY_EXPIRY_NOTIFIER_INTERVAL_SECONDS: default 300 (5 minutes)
- OUTBOUND_TEST_ALLOWLIST: comma-separated admin MSISDNs
"""

import asyncio
import logging
import os
from typing import Optional

from sqlalchemy import text

from app.outbound.factory import get_meta_client

# ---- Survey module imports (UPDATED ONLY) ----
from app.modules.survey.close_survey import close_survey_and_notify as close_survey
from app.modules.survey.summary import build_survey_summary_text

logger = logging.getLogger("survey_expiry_notifier")


def _env_flag(name: str, default: str = "1") -> bool:
    val = (os.getenv(name, default) or "").strip().lower()
    return val in ("1", "true", "yes", "y", "on")


def _get_interval_seconds() -> int:
    raw = (os.getenv("SURVEY_EXPIRY_NOTIFIER_INTERVAL_SECONDS", "300") or "").strip()
    try:
        n = int(raw)
        return max(30, n)  # never faster than 30s
    except Exception:
        return 300


def _get_admin_allowlist() -> set[str]:
    return {
        n.strip()
        for n in (os.getenv("OUTBOUND_TEST_ALLOWLIST", "") or "").split(",")
        if n.strip()
    }


async def _run_forever() -> None:
    """
    Runs forever in the background:
    - Find expired ACTIVE surveys
    - Close each
    - Send summary to admins
    """
    enabled = _env_flag("SURVEY_EXPIRY_NOTIFIER_ENABLED", "1")
    interval = _get_interval_seconds()

    logger.info(
        "EXPIRY_NOTIFIER_START | enabled=%s | interval_seconds=%s",
        enabled,
        interval,
    )

    if not enabled:
        logger.warning("EXPIRY_NOTIFIER_DISABLED | exiting")
        return

    try:
        from app.db import SessionLocal  # type: ignore
    except Exception as exc:
        logger.error("EXPIRY_NOTIFIER_NO_SESSIONLOCAL | error=%s", exc, exc_info=True)
        return

    meta = get_meta_client()

    while True:
        try:
            admin_allowlist = _get_admin_allowlist()
            if not admin_allowlist:
                logger.warning("EXPIRY_NOTIFIER_NO_ADMINS | OUTBOUND_TEST_ALLOWLIST empty")

            db = SessionLocal()
            try:
                rows = (
                    db.execute(
                        text(
                            """
                            SELECT id
                            FROM surveys
                            WHERE status = 'ACTIVE'
                              AND ends_at <= now()
                            ORDER BY ends_at ASC
                            LIMIT 50
                            """
                        )
                    )
                    .mappings()
                    .all()
                )

                logger.info("EXPIRY_SCAN | expired_active_found=%s", len(rows))

                for r in rows:
                    survey_id = r.get("id")
                    if not survey_id:
                        continue

                    survey = (
                        db.execute(
                            text(
                                """
                                SELECT *
                                FROM surveys
                                WHERE id = :id
                                """
                            ),
                            {"id": survey_id},
                        )
                        .mappings()
                        .first()
                    )

                    try:
                        from app.modules.survey.models import Survey  # type: ignore

                        obj: Optional[Survey] = db.get(Survey, survey_id)  # type: ignore[attr-defined]
                        if not obj:
                            logger.warning("EXPIRY_SURVEY_MISSING | survey_id=%s", survey_id)
                            continue

                        logger.info(
                            "EXPIRY_CLOSE_BEGIN | survey_id=%s | business=%s",
                            obj.id,
                            getattr(obj, "business_number", None),
                        )

                        close_survey(db=db, survey=obj, closed_by="auto")
                        logger.info("EXPIRY_CLOSED | survey_id=%s", obj.id)

                        summary = build_survey_summary_text(db, obj)
                        summary_single = " ".join((summary or "").split())

                        for admin in admin_allowlist:
                            try:
                                logger.info(
                                    "EXPIRY_NOTIFY_ADMIN | to=%s | survey_id=%s",
                                    admin,
                                    obj.id,
                                )
                                meta.send_generic_business_update_template(
                                    to_msisdn=admin,
                                    blob_text=summary_single,
                                )
                                logger.info(
                                    "EXPIRY_NOTIFY_ADMIN_OK | to=%s | survey_id=%s",
                                    admin,
                                    obj.id,
                                )
                            except Exception as exc:
                                logger.error(
                                    "EXPIRY_NOTIFY_ADMIN_FAIL | to=%s | survey_id=%s | error=%s",
                                    admin,
                                    obj.id,
                                    exc,
                                    exc_info=True,
                                )

                    except Exception as exc:
                        logger.error(
                            "EXPIRY_CLOSE_ORM_FAIL | survey_id=%s | error=%s",
                            survey_id,
                            exc,
                            exc_info=True,
                        )
                        try:
                            db.execute(
                                text(
                                    """
                                    UPDATE surveys
                                    SET status = 'CLOSED'
                                    WHERE id = :id
                                      AND status = 'ACTIVE'
                                    """
                                ),
                                {"id": survey_id},
                            )
                            db.commit()
                            logger.info("EXPIRY_CLOSED_SQL | survey_id=%s", survey_id)

                            msg = f"Survey auto-closed (expired). Survey ID: {survey_id}"
                            msg_single = " ".join(msg.split())

                            for admin in admin_allowlist:
                                try:
                                    meta.send_generic_business_update_template(
                                        to_msisdn=admin,
                                        blob_text=msg_single,
                                    )
                                except Exception:
                                    pass
                        except Exception as exc2:
                            logger.error(
                                "EXPIRY_CLOSE_SQL_FAIL | survey_id=%s | error=%s",
                                survey_id,
                                exc2,
                                exc_info=True,
                            )

            finally:
                try:
                    db.close()
                except Exception:
                    pass

        except Exception as exc:
            logger.error("EXPIRY_LOOP_FAIL | error=%s", exc, exc_info=True)

        await asyncio.sleep(interval)


def start_survey_expiry_notifier() -> None:
    """
    Call once at FastAPI startup.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        logger.warning("EXPIRY_NOTIFIER_NO_LOOP | cannot start (no running loop)")
        return

    logger.info("EXPIRY_NOTIFIER_SPAWN_TASK")
    asyncio.create_task(_run_forever())
