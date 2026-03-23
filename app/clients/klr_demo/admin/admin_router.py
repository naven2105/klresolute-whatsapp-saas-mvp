from __future__ import annotations

"""
File: admin_router.py
Path: app/clients/klr_demo/admin/admin_router.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
klr_demo admin command router.

Rules:
- Entry point for all admin messages
- Routes commands to appropriate handlers
- Returns admin menu for unknown commands
"""

from sqlalchemy.orm import Session

from app.clients.klr_demo.admin.admin_menu_service import handle_admin_menu
from app.clients.klr_demo.survey.survey_handler import handle_survey_command
from app.clients.klr_demo.handlers.campaign_handler import handle_admin_message

def route_admin_message(
    *,
    db: Session,
    sender_msisdn: str,
    business_msisdn: str,
    message_text: str | None,
    message_type: str,
    media_url: str | None,
) -> bool:

    msg = (message_text or "").strip()

    # --------------------------------------------------
    # SURVEY
    # --------------------------------------------------
    if handle_survey_command(
        db=db,
        sender_msisdn=sender_msisdn,
        business_msisdn=business_msisdn,
        message_text=msg,
    ):
        return True

    # --------------------------------------------------
    # CAMPAIGNS / ANNOUNCEMENTS
    # --------------------------------------------------
    if handle_admin_message(
        db=db,
        sender_msisdn=sender_msisdn,
        business_msisdn=business_msisdn,
        message_text=message_text,
        message_type=message_type,
        media_url=media_url,
    ):
        return True

    # --------------------------------------------------
    # UNKNOWN → ADMIN MENU
    # --------------------------------------------------
    return handle_admin_menu(
        db=db,
        sender_msisdn=sender_msisdn,
        business_msisdn=business_msisdn,
    )
