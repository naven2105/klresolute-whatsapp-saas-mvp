"""
File: app/services/outbound_delivery_service.py

Project: KLResolute WhatsApp SaaS MVP

Purpose:
T-14 / T-15 / T-16 Outbound Delivery Job Boundary (DRY-RUN ONLY) with Audit + Retry Semantics.

Responsibilities:
- Locate outbound Message drafts
- Perform a DRY-RUN delivery attempt (no external sending)
- Record immutable delivery audit events in delivery_events
- Enforce capped retry policy using delivery_events (source of truth)

Retry policy (CAPPED):
- Max attempts: 3
- Backoff: attempt2 after 5 minutes, attempt3 after 30 minutes
- After 3 attempts: record retry_exhausted once and stop
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Message, DeliveryEvent


# Retry policy
MAX_ATTEMPTS = 3
BACKOFF_AFTER_ATTEMPT_1 = timedelta(minutes=5)    # before attempt 2
BACKOFF_AFTER_ATTEMPT_2 = timedelta(minutes=30)   # before attempt 3

# Event types
EVENT_DRY_RUN_ATTEMPT = "dry_run_attempt"
EVENT_RETRY_ATTEMPT = "retry_attempt"
EVENT_RETRY_EXHAUSTED = "retry_exhausted"

ATTEMPT_EVENT_TYPES = (EVENT_DRY_RUN_ATTEMPT, EVENT_RETRY_ATTEMPT)


class OutboundDeliveryService:
    def __init__(self, db: Session | None = None) -> None:
        self._db = db

    def run_dry_run_delivery(self) -> int:
        """
        Manual job:
        - Attempts delivery for eligible outbound messages
        - Records delivery_events for every attempt
        - Enforces capped retries

        Returns:
            int: number of delivery attempts performed in this run
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

    # -----------------------------
    # Internal
    # -----------------------------
    def _attempt_if_eligible(self, session: Session, msg: Message, now_utc: datetime) -> bool:
        """
        Returns True if an attempt was performed (event written), else False.
        """
        attempts, last_attempt_at = self._get_attempt_state(session, msg.message_id)

        # Exhausted
        if attempts >= MAX_ATTEMPTS:
            self._ensure_exhausted_event(session, msg.message_id, attempts)
            return False

        # Backoff
        required_wait = self._required_wait(attempts)
        if last_attempt_at is not None and required_wait is not None:
            if (now_utc - last_attempt_at) < required_wait:
                return False

        # Perform attempt (dry-run only)
        event_type = EVENT_DRY_RUN_ATTEMPT if attempts == 0 else EVENT_RETRY_ATTEMPT
        detail = "not sent (dry-run)"

        session.add(
            DeliveryEvent(
                message_id=msg.message_id,
                event_type=event_type,
                event_detail=detail,
            )
        )

        # Track "last attempt time" using existing column (no schema changes)
        msg.sent_at = now_utc
        session.add(msg)

        return True

    def _get_attempt_state(self, session: Session, message_id) -> tuple[int, datetime | None]:
        """
        attempts = count of attempt events
        last_attempt_at = latest created_at among attempt events
        """
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
        """
        attempts is how many attempts have already happened.
        - attempts=0 -> attempt 1 allowed immediately
        - attempts=1 -> wait 5 minutes before attempt 2
        - attempts=2 -> wait 30 minutes before attempt 3
        """
        if attempts <= 0:
            return timedelta(seconds=0)
        if attempts == 1:
            return BACKOFF_AFTER_ATTEMPT_1
        if attempts == 2:
            return BACKOFF_AFTER_ATTEMPT_2
        return None

    def _ensure_exhausted_event(self, session: Session, message_id, attempts: int) -> None:
        """
        Record retry_exhausted once (idempotent).
        """
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
