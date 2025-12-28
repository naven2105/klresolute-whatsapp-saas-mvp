"""
File: app/models.py

Project: KLResolute WhatsApp SaaS MVP

Purpose:
SQLAlchemy ORM models defining the core data schema for the WhatsApp SaaS platform.
These models are the authoritative representation of the database structure and
must remain aligned with the BRS and schema definitions.

Design principles:
- Tables map 1:1 with BRS data entities
- No business logic in models
- Relationships kept minimal and explicit
- All writes are controlled by application logic, not model side-effects

Change control:
- Schema changes require explicit justification
- No fields may be removed without BRS update
"""


import uuid
from sqlalchemy import (
    Column,
    String,
    Text,
    Boolean,
    Integer,
    DateTime,
    Enum,
    ForeignKey,
    CheckConstraint,
    UniqueConstraint,
    Index,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


# ---------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------
class Client(Base):
    __tablename__ = "clients"

    client_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_name = Column(Text, nullable=False)
    status = Column(Text, nullable=False)
    trial_start_at = Column(DateTime(timezone=True), nullable=False)
    trial_end_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'inactive')",
            name="ck_clients_status",
        ),
        CheckConstraint(
            "trial_end_at > trial_start_at",
            name="ck_trial_dates",
        ),
    )


# ---------------------------------------------------------------------
# WhatsApp Number
# ---------------------------------------------------------------------
class WhatsAppNumber(Base):
    __tablename__ = "whatsapp_numbers"

    wa_number_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("clients.client_id"),
        nullable=False,
    )
    destination_number = Column(Text, nullable=False, unique=True)
    status = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'inactive')",
            name="ck_whatsapp_numbers_status",
        ),
    )

    client = relationship("Client")


# ---------------------------------------------------------------------
# Contact (global)
# ---------------------------------------------------------------------
class Contact(Base):
    __tablename__ = "contacts"

    contact_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contact_number = Column(Text, nullable=False, unique=True)
    display_name = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------------
# Conversation
# ---------------------------------------------------------------------
class Conversation(Base):
    __tablename__ = "conversations"

    conversation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("clients.client_id"),
        nullable=False,
    )
    wa_number_id = Column(
        UUID(as_uuid=True),
        ForeignKey("whatsapp_numbers.wa_number_id"),
        nullable=False,
    )
    contact_id = Column(
        UUID(as_uuid=True),
        ForeignKey("contacts.contact_id"),
        nullable=False,
    )

    status = Column(
        Enum("automated", "handed_over", "closed", name="conversation_status"),
        nullable=False,
        server_default="automated",
    )

    last_message_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    closed_at = Column(DateTime(timezone=True), nullable=True)

    client = relationship("Client")
    whatsapp_number = relationship("WhatsAppNumber")
    contact = relationship("Contact")


# Partial unique index: only one active conversation per wa_number + contact
Index(
    "uq_conversations_active",
    Conversation.wa_number_id,
    Conversation.contact_id,
    unique=True,
    postgresql_where=Conversation.closed_at.is_(None),
)


# ---------------------------------------------------------------------
# Message (immutable)
# ---------------------------------------------------------------------
class Message(Base):
    __tablename__ = "messages"

    message_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.conversation_id"),
        nullable=False,
    )

    direction = Column(
        Enum("inbound", "outbound", name="message_direction"),
        nullable=False,
    )

    message_text = Column(Text, nullable=False)
    provider_message_id = Column(Text, nullable=True)
    received_at = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    stored_at = Column(DateTime(timezone=True), server_default=func.now())

    conversation = relationship("Conversation")


# ---------------------------------------------------------------------
# Delivery Event (audit) — T-15 / T-16
# ---------------------------------------------------------------------
class DeliveryEvent(Base):
    __tablename__ = "delivery_events"

    delivery_event_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(
        UUID(as_uuid=True),
        ForeignKey("messages.message_id"),
        nullable=False,
    )
    event_type = Column(Text, nullable=False)
    event_detail = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Optional relationship (safe): helps joins, does not change schema
    message = relationship("Message")


# ---------------------------------------------------------------------
# FAQ Item
# ---------------------------------------------------------------------
class FaqItem(Base):
    __tablename__ = "faq_items"

    faq_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("clients.client_id"),
        nullable=False,
    )
    faq_name = Column(Text, nullable=False)
    match_pattern = Column(Text, nullable=False)
    response_text = Column(Text, nullable=False)
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "client_id",
            "faq_name",
            name="uq_faq_items_client_name",
        ),
    )

    client = relationship("Client")


# ---------------------------------------------------------------------
# Lead (immutable)
# ---------------------------------------------------------------------
class Lead(Base):
    __tablename__ = "leads"

    lead_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("clients.client_id"),
        nullable=False,
    )
    contact_id = Column(
        UUID(as_uuid=True),
        ForeignKey("contacts.contact_id"),
        nullable=False,
    )
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.conversation_id"),
        nullable=False,
    )

    lead_name = Column(Text, nullable=True)
    enquiry_text = Column(Text, nullable=False)
    captured_at = Column(DateTime(timezone=True), server_default=func.now())

    client = relationship("Client")
    contact = relationship("Contact")
    conversation = relationship("Conversation")


# ---------------------------------------------------------------------
# Event Log
# ---------------------------------------------------------------------
class EventLog(Base):
    __tablename__ = "event_logs"

    event_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("clients.client_id"),
        nullable=False,
    )
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.conversation_id"),
        nullable=True,
    )
    message_id = Column(
        UUID(as_uuid=True),
        ForeignKey("messages.message_id"),
        nullable=True,
    )

    event_type = Column(Text, nullable=False)
    event_detail = Column(Text, nullable=True)
    event_timestamp = Column(DateTime(timezone=True), server_default=func.now())

    client = relationship("Client")
