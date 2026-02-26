# ==================================================
# File: template_registry.py
# Path: app/messaging/template_registry.py
# Project: KLResolute WhatsApp SaaS MVP
#
# Sprint 12 – Backward Compatibility Patch
#
# Purpose:
# Centralised registry for all WhatsApp template names.
#
# Rules:
# - Constants only (no logic)
# - No hardcoded template strings elsewhere
# - Single source of truth for template references
# - Supports multi-tenant isolation
#
# Change:
# - Added ORDER_NOTIFICATION alias for backward compatibility
#   (used by legacy inbound import)
#
# Change Policy:
# - Do not remove templates without confirming usage
# - Marketing templates retained temporarily where required
# - Future upgrades must occur here first
# ==================================================

# ===============================
# FATGINGER
# ===============================

FG_ORDER_NOTIFICATION = "order_notification"

# Backward compatibility (legacy imports)
ORDER_NOTIFICATION = FG_ORDER_NOTIFICATION


# ===============================
# MAGEN
# ===============================

MAGEN_INSPECTION_COMPLETED = "magen_inspection_completed"


# ===============================
# PILATESHQ
# ===============================

PHQ_INVOICE_REVIEW_ADMIN = "invoice_review_admin_us"
PHQ_ADMIN_ALERT = "admin_generic_alert_us"
PHQ_SESSION_NEXT_HOUR = "client_session_next_hour_us"
PHQ_SESSION_TOMORROW = "client_session_tomorrow_us"
PHQ_ADMIN_MORNING = "admin_morning_us"
PHQ_ADMIN_EVENING = "admin_20h00_us"
PHQ_CLIENT_REGISTRATION = "client_registration"


# ===============================
# GENERIC / PLATFORM
# ===============================

PLATFORM_ADMIN_FEEDBACK = "admin_feedback_alert"
PLATFORM_CLIENT_GENERIC = "client_generic_alert_us"


# ===============================
# CAMPAIGN (TEMPORARY – TO BE UPGRADED)
# ===============================

FG_CAMPAIGN_TEMPLATE = "generic_business_update"