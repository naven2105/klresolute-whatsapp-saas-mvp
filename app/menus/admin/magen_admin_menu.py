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

GUARD RAILS:
- No dynamic behaviour
- No DB access
- No outbound messaging
- Safe to import anywhere
"""

import logging

logger = logging.getLogger("menus.admin.galitos")

GALITOS_ADMIN_MENU = {
    "title": "🛠️ Admin Menu",
    "sections": [
        {
            "title": "📊 Surveys",
            "commands": [
                "Start surveys (one active at a time):",
                "",
                "SURVEY SENTIMENT: <question>",
                "👍 Like   😐 Neutral   👎 Dislike",
                "",
                "SURVEY FREQUENCY: <question>",
                "🔁 Often   ➖ Sometimes   ⏳ Rarely",
                "",
                "SURVEY HELPFULNESS: <question>",
                "✅ Helpful   😐 Neutral   ❌ Not Helpful",
                "",
                "END SURVEY",
                "",
                "Notes:",
                "• Surveys auto-close in 24 hours",
                "• Starting a new survey closes the previous one",
                "• Survey results are shared with admins when the survey closes",
            ],
        },
        {
            "title": "🎯 Announcement",
            "commands": [
                "Send an image with a caption to activate a new announcement.",
                "",
                "Notes:",
                "• Only ONE announcement at a time",
                "• A new image replaces the previous one",
                "• Customers use “announcements” to view the latest announcement",
            ],
        },
    ],
}

logger.info("GALITOS_ADMIN_MENU_LOADED")
