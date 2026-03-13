# ==================================================
# File: rusticbarrel_admin_menu.py
# Path: app/menus/admin/rusticbarrel_admin_menu.py
# Project: KLResolute WhatsApp SaaS MVP
#
# Sprint 34 – Rustic Barrel Admin Menu
#
# Purpose:
# Configuration-only admin menu definition for Rustic Barrel.
#
# Rules:
# - No logic
# - No database access
# - Pure configuration
# ==================================================

RUSTICBARREL_ADMIN_MENU = {
    "text": """
🛠️ Rustic Barrel Admin Menu

📊 Surveys

Start a survey:

SURVEY: <question>

Example:
SURVEY: How was your meal today?

Customers can reply:
Positive
Neutral
Negative

END SURVEY

Notes:
• Only one active survey at a time
• Surveys auto-close after 24 hours
• Results are shared automatically when closed

────────────────

🎯 Announcement

Send an image with a caption to activate/update announcement.

Notes:
• Only one active announcement
• A new image replaces the previous one
• Customers type: announcements
""".strip()
}