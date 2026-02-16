from __future__ import annotations

"""
File: app/menus/admin/galitos_admin_menu.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Admin menu definition for Galitos (retail client).

EXPLICIT ROLE:
- This file defines the Galitos admin menu ONLY
- Menu is hard-coded by design
- Menu text is instructional, not command-parsed
- Announcements are triggered by admin sending IMAGE + CAPTION only

GUARD RAILS:
- No dynamic behaviour
- No DB access
- No outbound messaging
- Safe to import anywhere
"""

import logging

logger = logging.getLogger("menus.admin.galitos")

# Single source of truth for the admin menu text (canonical).
# Handlers must not hardcode menu text.
_GALITOS_ADMIN_MENU_TEXT = (
    "🛠️ Admin Menu\n\n"
    "📊 Surveys\n\n"
    "Start surveys (one active at a time):\n\n"
    "SURVEY SENTIMENT: <question>\n"
    "👍 Like   😐 Neutral   👎 Dislike\n\n"
    "SURVEY FREQUENCY: <question>\n"
    "🔁 Often   ➖ Sometimes   ⏳ Rarely\n\n"
    "SURVEY HELPFULNESS: <question>\n"
    "✅ Helpful   😐 Neutral   ❌ Not Helpful\n\n"
    "END SURVEY\n\n"
    "Notes:\n"
    "• Surveys auto-close in 24 hours\n"
    "• Starting a new survey closes the previous one\n"
    "• Survey results are shared with admins when the survey closes\n\n"
    "────────────────\n\n"
    "🎯 Announcement\n\n"
    "Send an image with a caption to activate a new announcement.\n\n"
    "Notes:\n"
    "• Only ONE announcement at a time\n"
    "• A new image replaces the previous one\n"
    "• Customers use “announcements” to view the latest announcement"
)

GALITOS_ADMIN_MENU = {
    # Preferred canonical representation for exact WhatsApp output
    "text": _GALITOS_ADMIN_MENU_TEXT,

    # Kept for backwards compatibility / future structured formatting
    "title": "🛠️ Galitos Admin Menu",
    "sections": [
        {
            "title": "🛠️ Surveys",
            "commands": [
                "SEND SURVEY",
                "CLOSE SURVEY",
            ],
        },
        {
            "title": "👥 Customers",
            "commands": [
                "ADD CUSTOMER: <number>",
                "REMOVE CUSTOMER: <number>",
                "COUNT CUSTOMERS",
            ],
        },
        {
            "title": "✉️ Messaging",
            "commands": [
                "SEND: <number> <message>",
            ],
        },
        {
            "title": "🖼️ Announcements",
            "commands": [
                "Send image with caption to publish announcement",
                "Latest announcement replaces previous one",
            ],
        },
        {
            "title": "🏗️ Site Inspections",
            "commands": [
                "START INSPECTION",
                "UPLOAD PHOTOS",
                "SUBMIT CHECKLIST",
            ],
        },
        {
            "title": "⚙️ System",
            "commands": [
                "PAUSE",
                "RESUME",
            ],
        },
    ],
}

logger.info("GALITOS_ADMIN_MENU_LOADED")
