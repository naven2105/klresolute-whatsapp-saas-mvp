"""
File: app/services/outbound_delivery_service.py

Project: KLResolute WhatsApp SaaS MVP

Purpose:
T-14 / T-15 / T-16 / T-25
Outbound Delivery Job Boundary with Gateway Wiring (SAFE BY DEFAULT)

Responsibilities:
- Locate outbound Message drafts
- Decide if delivery attempt is eligible
- Invoke outbound gateway (DRY-RUN by default)
- Record immutable delivery audit events in delivery_events
- Enforce capped retry policy using delivery_events

IMPORTANT:
- Real sending is DISABLED unless explicitly enabled via env
- Webhooks NEVER call the gateway directly
"""

from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Message, DeliveryEvent
from app.outbound.factory import (
    OutboundDeliverySettings,
    build_send_gateway,
)
from app.outbound.gateway import SendStatus


# ------------------------------------------------------------------
# Retry policy
# ------------------------------------------------------------------
MAX_ATTEMPTS = 3
BACKOFF_AFTER_ATTEMPT_1 = timedelta(minutes=5)
BACKOFF_AFTER_ATTEMPT_2 = timedelta(minutes=30)

EVENT_DRY_RUN_ATTEMPT = "dry_run_attempt"
EVENT_RETRY_ATTEMPT = "retry_attempt"
EVENT_RETRY_EXHAUSTED = "retry_exhausted"

ATTEMPT_EVENT_TYPES = (EVENT_DRY_RUN_ATTEMPT, EVENT_RETRY_ATTEMPT)


class OutboundDeliveryService:
    def __init__(self, db: Session | None = None) -> None:
        self._db = db

        # --------------------------------------------------------------
        # T-25: Build outbound delivery gateway (SAFE DEFAULTS)
        # --------------------------------------------------------------
        settings = OutboundDeliverySettings(
            mode=os.getenv("OUTBOUND_MODE", "dry_run"),
            meta_enabled=os.getenv("META_SEND_ENABLED", "false").lower() == "true",
            meta_access_token=os.getenv("META_ACCESS_TOKEN"),
            meta_phone_number_id=os.getenv("META_PHONE_NUMBER_ID"),
            meta_api_base_url=os.getenv(
                "META_API_BASE_URL", "https://graph.facebook.com/v23.0"
            ),
            test_allowlist=tuple(
                n.strip()
                for n in os.getenv("OUTBOUND_TEST_ALLOWLIST", "").split(",")
                if n.strip()
            ),
        )

        self._gateway = build_send_gateway(settings)

    # ------------------------------------------------------------------
    # Public job entry
    # ------------------------------------------------------------------
    def run_delivery(self) -> int:
        """
        Manual / scheduled job.
        Attempts outbound delivery for eligible messages.
        """
        session = self._db or SessionLocal()
        performed_attempts = 0
        now_utc = datetime.now(timezone.utc)

        try:
            outbound_messages = (
                session.query(Message)
                .filter(Message.direction == "outbound")
                .order_by(Message.stored_at.asc())
                .all()
            )

            for msg in outbound_messages:
                if self._attempt_if_eligible(session, msg, now_utc):
                    performed_attempts += 1

            session.commit()
            return performed_attempts

        finally:
            if self._db is None:
                session.close()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _attempt_if_eligible(
        self,
        session: Session,
        msg: Message,
        now_utc: datetime,
    ) -> bool:
        attempts, last_attempt_at = self._get_attempt_state(session, msg.message_id)

        if attempts >= MAX_ATTEMPTS:
            self._ensure_exhausted_event(session, msg.message_id, attempts)
            return False

        required_wait = self._required_wait(attempts)
        if last_attempt_at and required_wait:
            if (now_utc - last_attempt_at) < required_wait:
                return False

        # --------------------------------------------------------------
        # Invoke gateway (still DRY-RUN unless enabled)
        # --------------------------------------------------------------
        receipt = self._gateway.send_text(
            req=msg.to_send_request()
        )

        event_type = (
            EVENT_DRY_RUN_ATTEMPT
            if receipt.status in (SendStatus.DISABLED, SendStatus.FAILED)
            else EVENT_RETRY_ATTEMPT
        )

        session.add(
            DeliveryEvent(
                message_id=msg.message_id,
                event_type=event_type,
                event_detail=receipt.detail,
            )
        )

        msg.sent_at = now_utc
        session.add(msg)

        return True

    def _get_attempt_state(
        self, session: Session, message_id
    ) -> tuple[int, datetime | None]:
        attempts = (
            session.query(func.count(DeliveryEvent.delivery_event_id))
            .filter(
                DeliveryEvent.message_id == message_id,
                DeliveryEvent.event_type.in_(ATTEMPT_EVENT_TYPES),
            )
            .scalar()
        ) or 0

        last_attempt_at = (
            session.query(func.max(DeliveryEvent.created_at))
            .filter(
                DeliveryEvent.message_id == message_id,
                DeliveryEvent.event_type.in_(ATTEMPT_EVENT_TYPES),
            )
            .scalar()
        )

        return int(attempts), last_attempt_at

    def _required_wait(self, attempts: int) -> timedelta | None:
        if attempts <= 0:
            return timedelta(seconds=0)
        if attempts == 1:
            return BACKOFF_AFTER_ATTEMPT_1
        if attempts == 2:
            return BACKOFF_AFTER_ATTEMPT_2
        return None

    def _ensure_exhausted_event(
        self, session: Session, message_id, attempts: int
    ) -> None:
        existing = (
            session.query(DeliveryEvent)
            .filter(
                DeliveryEvent.message_id == message_id,
                DeliveryEvent.event_type == EVENT_RETRY_EXHAUSTED,
            )
            .first()
        )
        if existing:
            return

        session.add(
            DeliveryEvent(
                message_id=message_id,
                event_type=EVENT_RETRY_EXHAUSTED,
                event_detail=f"max attempts reached ({attempts})",
            )
        )
