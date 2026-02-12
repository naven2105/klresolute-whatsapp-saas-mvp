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
- Specials are triggered by admin sending IMAGE + CAPTION only

GUARD RAILS:
- No dynamic behaviour
- No DB access
- No outbound messaging
- Safe to import anywhere

CHANGE NOTE:
- Removed STATUS / CLEAR STATUS
- Removed SEND / broadcast references
- Removed "No active survey" indicator
- Specials reworded to image + caption trigger
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
            "title": "🎯 Special",
            "commands": [
                "Send an image with a caption to activate a new special.",
                "",
                "Notes:",
                "• Only ONE special at a time",
                "• A new image replaces the previous one",
                "• Customers use “specials” to view the latest special",
            ],
        },
    ],
}

logger.info("GALITOS_ADMIN_MENU_LOADED")
