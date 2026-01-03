"""
File: app/services/contacts_service.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Shared contact service.

This is the ONLY place allowed to:
- add a contact
- remove a contact
- check if a contact exists

Used by:
- admin_commands.py
- client_commands.py

Design rules:
- Idempotent operations
- No messaging
- No business policy
- DB is source of truth
"""

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models import Contact


# -------------------------------------------------
# Queries
# -------------------------------------------------

def contact_exists(db: Session, *, msisdn: str) -> bool:
    return (
        db.query(Contact)
        .filter(Contact.contact_number == msisdn)
        .one_or_none()
        is not None
    )


# -------------------------------------------------
# Commands
# -------------------------------------------------

def add_contact(db: Session, *, msisdn: str) -> bool:
    """
    Adds a contact if it does not exist.

    Returns:
        True  -> contact was added
        False -> contact already existed
    """
    if contact_exists(db, msisdn=msisdn):
        return False

    try:
        db.add(Contact(contact_number=msisdn))
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        return False


def remove_contact(db: Session, *, msisdn: str) -> bool:
    """
    Removes a contact if it exists.

    Returns:
        True  -> contact was removed
        False -> contact did not exist
    """
    contact = (
        db.query(Contact)
        .filter(Contact.contact_number == msisdn)
        .one_or_none()
    )

    if not contact:
        return False

    db.delete(contact)
    db.commit()
    return True
