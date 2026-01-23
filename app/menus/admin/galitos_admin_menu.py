"""
File: app/menus/admin/galitos_admin_menu.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Admin menu definition for Galitos (retail client).
Full admin capabilities.
"""

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
                "BROADCAST: <message>",
            ],
        },
        {
            "title": "🖼️ Specials",
            "commands": [
                "SEND SPECIAL (image + caption)",
                "REPLAY SPECIAL",
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
