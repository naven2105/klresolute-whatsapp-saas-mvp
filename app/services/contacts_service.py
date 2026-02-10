"""
File: app/services/contacts_service.py
Project: KLResolute WhatsApp SaaS MVP

ROLE (EXPLICIT & LOCKED):
This module is the SINGLE AUTHORITY for contact persistence.

It is intentionally:
- Silent (never sends messages)
- Idempotent
- Policy-free
- Admin-safe

This module MUST:
- Never raise exceptions to callers
- Never break upstream flows
- Treat the database as the only source of truth

This is the ONLY place allowed to:
- add a contact
- remove a contact
- check if a contact exists

Used by:
- admin_commands.py
- client_commands.py

Design rules (LOCKED):
- Idempotent operations
- No messaging
- No business policy
- DB is source of truth
- Guarded execution (errors logged, never propagated)
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models import Contact


# -------------------------------------------------
# Logging
# -------------------------------------------------

logger = logging.getLogger("services.contacts")


# -------------------------------------------------
# Queries
# -------------------------------------------------

def contact_exists(db: Session, *, msisdn: str) -> bool:
    """
    Check if a contact exists.

    Guard rails:
    - Never raises
    - Returns False on any failure
    """
    try:
        return (
            db.query(Contact)
            .filter(Contact.contact_number == msisdn)
            .one_or_none()
            is not None
        )
    except Exception:
        logger.exception(
            "contact_exists failed",
            extra={"msisdn": msisdn},
        )
        return False


# -------------------------------------------------
# Commands
# -------------------------------------------------

def add_contact(db: Session, *, msisdn: str) -> bool:
    """
    Adds a contact if it does not exist.

    Returns:
        True  -> contact was added
        False -> contact already existed OR operation failed

    Guard rails:
    - Never raises
    - Silent failure (logged only)
    """
    try:
        if contact_exists(db, msisdn=msisdn):
            return False

        try:
            db.add(Contact(contact_number=msisdn))
            db.commit()
            return True
        except IntegrityError:
            db.rollback()
            return False

    except Exception:
        logger.exception(
            "add_contact failed",
            extra={"msisdn": msisdn},
        )
        try:
            db.rollback()
        except Exception:
            pass
        return False


def remove_contact(db: Session, *, msisdn: str) -> bool:
    """
    Removes a contact if it exists.

    Returns:
        True  -> contact was removed
        False -> contact did not exist OR operation failed

    Guard rails:
    - Never raises
    - Silent failure (logged only)
    """
    try:
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

    except Exception:
        logger.exception(
            "remove_contact failed",
            extra={"msisdn": msisdn},
        )
        try:
            db.rollback()
        except Exception:
            pass
        return False
