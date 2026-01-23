"""
File: app/menus/customers/galitos_customer_menu.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Customer-facing menu for Galitos.
"""

GALITOS_CUSTOMER_MENU = {
    "title": "📋 MENU",
    "sections": [
        {
            "title": "👋 Welcome!",
            "commands": [
                '"ABOUT" – Store information',
                '"JOIN" – Receive store updates',
                '"STOP" – Opt out of updates',
                '"FEEDBACK" – Type: FEEDBACK: your message',
                '"MENU" – Show this menu again',
                '"FOOD" – Order ONE food item (for multiple items, call store)',
                '"HOURS" – Store hours',
                '"SPECIALS" – Today’s specials',
            ],
        },
        {
            "title": "📊 Surveys",
            "commands": [
                "From time to time, you may receive a short survey.",
                "Please tap the buttons to respond — it only takes a second.",
            ],
        },
    ],
}
