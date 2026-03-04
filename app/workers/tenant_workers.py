# ==================================================
# File: tenant_workers.py
# Path: app/workers/tenant_workers.py
# Project: KLResolute WhatsApp SaaS MVP
#
# Purpose:
# Central registry for tenant background workers.
#
# Rules:
# - Each tenant registers its own workers
# - No cross-tenant imports
# - Platform starts all workers from here
# ==================================================

from __future__ import annotations

import logging

logger = logging.getLogger("tenant_workers")


def start_all_workers() -> None:
    """
    Starts all tenant background workers.
    """

    logger.info("TENANT_WORKERS_START")

    # ----------------------------------------
    # FatGinger workers
    # ----------------------------------------
    try:
        from app.clients.fatginger.survey.survey_expiry_notifier import (
            start_survey_expiry_notifier,
        )

        start_survey_expiry_notifier()

        logger.info("TENANT_WORKER_STARTED | tenant=fatginger | worker=survey_expiry")

    except Exception:
        logger.exception("TENANT_WORKER_FAIL | tenant=fatginger")

    # ----------------------------------------
    # Galitos workers
    # ----------------------------------------
    try:
        from app.clients.galitos.survey.survey_expiry_notifier import (
            start_survey_expiry_notifier,
        )

        start_survey_expiry_notifier()

        logger.info("TENANT_WORKER_STARTED | tenant=galitos | worker=survey_expiry")

    except Exception:
        logger.exception("TENANT_WORKER_FAIL | tenant=galitos")

    # ----------------------------------------
    # Magen workers
    # ----------------------------------------
    try:
        from app.clients.magen.survey.survey_expiry_notifier import (
            start_survey_expiry_notifier,
        )

        start_survey_expiry_notifier()

        logger.info("TENANT_WORKER_STARTED | tenant=magen | worker=survey_expiry")

    except Exception:
        logger.exception("TENANT_WORKER_FAIL | tenant=magen")

    # ----------------------------------------
    # PilatesHQ workers
    # ----------------------------------------
    try:
        from app.clients.pilateshq.survey.survey_expiry_notifier import (
            start_survey_expiry_notifier,
        )

        start_survey_expiry_notifier()

        logger.info("TENANT_WORKER_STARTED | tenant=pilateshq | worker=survey_expiry")

    except Exception:
        logger.exception("TENANT_WORKER_FAIL | tenant=pilateshq")