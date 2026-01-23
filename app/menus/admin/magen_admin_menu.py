"""
File: app/menus/admin/magen_admin_menu.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Admin menu definition for Magen Security.
Manager / supervisor capabilities.
"""

MAGEN_ADMIN_MENU = {
    "title": "🛠️ Magen Admin Menu",
    "sections": [
        {
            "title": "✉️ Messaging",
            "commands": [
                "BROADCAST: <message>",
            ],
        },
        {
            "title": "🏗️ Security Inspections",
            "commands": [
                "START INSPECTION",
                "UPLOAD PHOTOS",
                "SUBMIT REPORT",
            ],
        },
        {
            "title": "👮 Officers",
            "commands": [
                "ADD OFFICER: <number>",
                "REMOVE OFFICER: <number>",
                "LIST OFFICERS",
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
