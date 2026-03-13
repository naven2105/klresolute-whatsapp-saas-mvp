# ==================================================
# File: template_registry.py
# Path: app/messaging/template_registry.py
# Project: KLResolute WhatsApp SaaS MVP
#
# Sprint 12 – Template Governance Update
#
# Purpose:
# Centralised registry for all WhatsApp template names.
#
# Rules:
# - Constants only (no logic)
# - No hardcoded template strings elsewhere
# - Single source of truth
# ==================================================

# ===============================
# FATGINGER
# ===============================

FG_ORDER_NOTIFICATION = "order_notification"


# ===============================
# RUSTIC BARREL
# ===============================

RUSTICBARREL_NOTIFICATION = "klr_notification_v1"


# ===============================
# ZAR
# ===============================

ZAR_CAMPAIGN_TEMPLATE = "generic_business_update"


# ===============================
# SURVEY (Marketing)
# ===============================

SURVEY_TEMPLATE_V1 = "survey_v1"


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