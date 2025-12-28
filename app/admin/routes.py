"""
File: app/admin/routes.py

Project: KLResolute WhatsApp SaaS MVP

Purpose:
Admin visibility and control endpoints.

Endpoints:
- GET  /admin/conversations
- GET  /admin/conversations/{conversation_id}/messages
- GET  /admin/messages/{message_id}/delivery-events
- GET  /admin/summary/outbound
- GET  /admin/conversations/{conversation_id}/summary
- POST /admin/conversations/{conversation_id}/handover   (T-22)

Design rules:
- Read-only by default
- Explicit, controlled writes only where stated
- No outbound sending
- Safe for MVP operations
"""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db import get_db
from app.models import Conversation, Message, DeliveryEvent

router = APIRouter(prefix="/admin", tags=["admin"])


# -------------------------------------------------------------------
# Conversations
# -------------------------------------------------------------------
@router.get("/conversations")
def list_conversations(db: Session = Depends(get_db)):
    rows = (
        db.query(
            Conversation.conversation_id,
            Conversation.client_id,
            Conversation.contact_id,
            Conversation.status,
            Conversation.created_at,
            Conversation.closed_at,
        )
        .order_by(Conversation.created_at.desc())
        .limit(50)
        .all()
    )

    return [
        {
            "conversation_id": r.conversation_id,
            "client_id": r.client_id,
            "contact_id": r.contact_id,
            "status": r.status,
            "created_at": r.created_at,
            "closed_at": r.closed_at,
        }
        for r in rows
    ]


# -------------------------------------------------------------------
# Messages per conversation
# -------------------------------------------------------------------
@router.get("/conversations/{conversation_id}/messages")
def list_conversation_messages(
    conversation_id: UUID,
    db: Session = Depends(get_db),
):
    rows = (
        db.query(
            Message.message_id,
            Message.direction,
            Message.message_text,
            Message.provider_message_id,
            Message.received_at,
            Message.sent_at,
            Message.stored_at,
        )
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.stored_at.asc())
        .all()
    )

    return [
        {
            "message_id": r.message_id,
            "direction": r.direction,
            "message_text": r.message_text,
            "provider_message_id": r.provider_message_id,
            "received_at": r.received_at,
            "sent_at": r.sent_at,
            "stored_at": r.stored_at,
        }
        for r in rows
    ]


# -------------------------------------------------------------------
# Delivery events per message
# -------------------------------------------------------------------
@router.get("/messages/{message_id}/delivery-events")
def list_delivery_events(
    message_id: UUID,
    db: Session = Depends(get_db),
):
    rows = (
        db.query(
            DeliveryEvent.delivery_event_id,
            DeliveryEvent.event_type,
            DeliveryEvent.event_detail,
            DeliveryEvent.created_at,
        )
        .filter(DeliveryEvent.message_id == message_id)
        .order_by(DeliveryEvent.created_at.asc())
        .all()
    )

    return [
        {
            "delivery_event_id": r.delivery_event_id,
            "event_type": r.event_type,
            "event_detail": r.event_detail,
            "created_at": r.created_at,
        }
        for r in rows
    ]


# -------------------------------------------------------------------
# T-19: Outbound delivery summary
# -------------------------------------------------------------------
@router.get("/summary/outbound")
def outbound_summary(db: Session = Depends(get_db)):
    return {
        "total_outbound_messages": db.query(func.count(Message.message_id))
        .filter(Message.direction == "outbound")
        .scalar()
        or 0,
        "outbound_with_delivery_events": db.query(
            func.count(func.distinct(DeliveryEvent.message_id))
        ).scalar()
        or 0,
        "total_delivery_events": db.query(
            func.count(DeliveryEvent.delivery_event_id)
        ).scalar()
        or 0,
        "latest_outbound_at": db.query(func.max(Message.stored_at))
        .filter(Message.direction == "outbound")
        .scalar(),
    }


# -------------------------------------------------------------------
# T-20: Per-conversation summary
# -------------------------------------------------------------------
@router.get("/conversations/{conversation_id}/summary")
def conversation_summary(
    conversation_id: UUID,
    db: Session = Depends(get_db),
):
    conversation = (
        db.query(Conversation)
        .filter(Conversation.conversation_id == conversation_id)
        .one()
    )

    inbound_count = (
        db.query(func.count(Message.message_id))
        .filter(
            Message.conversation_id == conversation_id,
            Message.direction == "inbound",
        )
        .scalar()
        or 0
    )

    outbound_count = (
        db.query(func.count(Message.message_id))
        .filter(
            Message.conversation_id == conversation_id,
            Message.direction == "outbound",
        )
        .scalar()
        or 0
    )

    last_inbound = (
        db.query(Message.message_text)
        .filter(
            Message.conversation_id == conversation_id,
            Message.direction == "inbound",
        )
        .order_by(Message.stored_at.desc())
        .first()
    )

    last_outbound = (
        db.query(Message.message_text)
        .filter(
            Message.conversation_id == conversation_id,
            Message.direction == "outbound",
        )
        .order_by(Message.stored_at.desc())
        .first()
    )

    last_activity = (
        db.query(func.max(Message.stored_at))
        .filter(Message.conversation_id == conversation_id)
        .scalar()
    )

    return {
        "conversation_id": conversation_id,
        "status": conversation.status,
        "inbound_count": inbound_count,
        "outbound_count": outbound_count,
        "last_inbound_text": last_inbound[0] if last_inbound else None,
        "last_outbound_text": last_outbound[0] if last_outbound else None,
        "last_activity_at": last_activity,
    }


# -------------------------------------------------------------------
# T-22: Conversation handover (controlled write)
# -------------------------------------------------------------------
@router.post("/conversations/{conversation_id}/handover")
def handover_conversation(
    conversation_id: UUID,
    db: Session = Depends(get_db),
):
    conversation = (
        db.query(Conversation)
        .filter(Conversation.conversation_id == conversation_id)
        .one_or_none()
    )

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if conversation.status == "handed_over":
        return {
            "conversation_id": conversation_id,
            "status": conversation.status,
            "note": "Already handed over",
        }

    conversation.status = "handed_over"
    db.commit()

    return {
        "conversation_id": conversation_id,
        "status": conversation.status,
        "note": "Conversation handed over to human",
    }
