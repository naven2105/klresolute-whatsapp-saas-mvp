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
- Removed BROADCAST command reference
- Reworded Specials to guidance-only (no command implication)
"""

import logging

logger = logging.getLogger("menus.admin.galitos")

GALITOS_ADMIN_MENU = {
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
            "title": "🖼️ Specials",
            "commands": [
                "Send image with caption to publish special",
                "Latest special replaces previous one",
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
