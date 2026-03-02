from __future__ import annotations

"""
File: app/clients/galitos/survey/survey_expiry_notifier.py
Path: app/clients/galitos/survey/survey_expiry_notifier.py
Project: KLResolute WhatsApp SaaS MVP

Sprint: Full UUID Identity Migration

Purpose:
Background notifier that auto-closes expired ACTIVE surveys and notifies admins.

Changes:
- UUID-only admin resolution
- Business-scoped client_id lookup
- No client_code usage
- Behaviour unchanged
"""

import asyncio
import logging
import os
from typing import Optional

from sqlalchemy import text

from app.outbound.factory import get_meta_client
from app.clients.galitos.survey.close_survey import close_survey_and_notify as close_survey
from app.clients.galitos.survey.summary import build_survey_summary_text
from app.messaging.template_registry import FG_CAMPAIGN_TEMPLATE

logger = logging.getLogger("survey_expiry_notifier")


def _env_flag(name: str, default: str = "1") -> bool:
    val = (os.getenv(name, default) or "").strip().lower()
    return val in ("1", "true", "yes", "y", "on")


def _get_interval_seconds() -> int:
    raw = (os.getenv("SURVEY_EXPIRY_NOTIFIER_INTERVAL_SECONDS", "300") or "").strip()
    try:
        return max(30, int(raw))
    except Exception:
        return 300


async def _run_forever() -> None:
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
        from app.db import SessionLocal
    except Exception as exc:
        logger.error("EXPIRY_NOTIFIER_NO_SESSIONLOCAL | error=%s", exc, exc_info=True)
        return

    while True:
        try:
            db = SessionLocal()
            try:
                rows = (
                    db.execute(
                        text(
                            """
                            SELECT id, business_number
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
                    business_number = r.get("business_number")

                    if not survey_id or not business_number:
                        continue

                    try:
                        from app.clients.galitos.survey.survey_models import Survey

                        obj: Optional[Survey] = db.get(Survey, survey_id)
                        if not obj:
                            logger.warning("EXPIRY_SURVEY_MISSING | survey_id=%s", survey_id)
                            continue

                        logger.info(
                            "EXPIRY_CLOSE_BEGIN | survey_id=%s | business=%s",
                            obj.id,
                            business_number,
                        )

                        close_survey(db=db, survey=obj, closed_by="auto")

                        logger.info("EXPIRY_CLOSED | survey_id=%s", obj.id)

                        summary = build_survey_summary_text(db, obj)
                        summary_single = " ".join((summary or "").split())

                        meta = get_meta_client(
                            db=db,
                            business_msisdn=business_number,
                        )

                        # Resolve client_id from whatsapp_numbers
                        client_row = (
                            db.execute(
                                text(
                                    """
                                    SELECT client_id
                                    FROM whatsapp_numbers
                                    WHERE destination_number = :business
                                      AND status = 'active'
                                    LIMIT 1
                                    """
                                ),
                                {"business": business_number},
                            )
                            .mappings()
                            .first()
                        )

                        if not client_row:
                            logger.error(
                                "EXPIRY_CLIENT_RESOLUTION_FAIL | business=%s",
                                business_number,
                            )
                            continue

                        client_id = str(client_row["client_id"])

                        admins = (
                            db.execute(
                                text(
                                    """
                                    SELECT msisdn
                                    FROM client_admins
                                    WHERE client_id = :client_id
                                      AND is_active = TRUE
                                    """
                                ),
                                {"client_id": client_id},
                            )
                            .scalars()
                            .all()
                        )

                        for admin in admins:
                            try:
                                meta.send_template(
                                    to_msisdn=admin,
                                    template_name=FG_CAMPAIGN_TEMPLATE,
                                    body_params=[summary_single],
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
                        db.rollback()
                        logger.error(
                            "EXPIRY_CLOSE_FAIL | survey_id=%s | error=%s",
                            survey_id,
                            exc,
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
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        logger.warning("EXPIRY_NOTIFIER_NO_LOOP | cannot start (no running loop)")
        return

    logger.info("EXPIRY_NOTIFIER_SPAWN_TASK")
    asyncio.create_task(_run_forever())