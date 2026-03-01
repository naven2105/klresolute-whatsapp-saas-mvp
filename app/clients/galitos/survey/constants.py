from __future__ import annotations

"""
File: app/modules/survey/constants.py
Path: app/modules/survey/constants.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Survey constants (module-authoritative).

MVP Simplified:
- Single survey type only
- 3 fixed responses: POSITIVE / NEUTRAL / NEGATIVE
- No legacy survey modes

Rules:
- Constants only
- No logic
"""

DEFAULT_SURVEY_DURATION_HOURS = 24

SURVEY_STATUS_ACTIVE = "ACTIVE"
SURVEY_STATUS_CLOSED = "CLOSED"

# -------------------------------------------------
# SINGLE STANDARD BUTTON SET (MVP)
# -------------------------------------------------

SURVEY_BUTTON_SETS = {
    "STANDARD": {
        "label": "Standard",
        "buttons": [
            {"id": "POSITIVE", "text": "Positive", "tag": "POSITIVE"},
            {"id": "NEUTRAL", "text": "Neutral", "tag": "NEUTRAL"},
            {"id": "NEGATIVE", "text": "Negative", "tag": "NEGATIVE"},
        ],
    },
}

# -------------------------------------------------
# Commands
# -------------------------------------------------

SURVEY_COMMAND_START = "SURVEY"
SURVEY_COMMAND_END = "END SURVEY"

SUPPORTED_SURVEY_COMMANDS = {
    SURVEY_COMMAND_START: "STANDARD",
}

# -------------------------------------------------
# Admin Templates
# -------------------------------------------------

ADMIN_SURVEY_STARTED_TEMPLATE = (
    "✅ Survey started\n\n"
    "Question:\n"
    "{question}\n\n"
    "This survey will run for 24 hours and has been sent to all opted-in clients.\n"
    "You will receive a summary automatically when it ends."
)

ADMIN_SURVEY_ALREADY_ACTIVE_TEMPLATE = (
    "⚠️ Survey already active\n\n"
    "There is an active survey running:\n"
    "{question}\n\n"
    "Time remaining: {hours_remaining} hours\n\n"
    "Please wait for it to end, or send:\n"
    "END SURVEY"
)

ADMIN_SURVEY_NO_ACTIVE_TEMPLATE = (
    "ℹ️ No active survey\n\n"
    "There is currently no active survey running."
)

ADMIN_SURVEY_SUMMARY_TEMPLATE = (
    "📊 Survey closed\n\n"
    "Question:\n"
    "{question}\n\n"
    "Responses ({total} total):\n"
    "{results}"
)

# -------------------------------------------------
# Customer Messages
# -------------------------------------------------

CUSTOMER_SURVEY_THANK_YOU_TEMPLATE = "Thanks for your feedback 👍"

# -------------------------------------------------
# Flags
# -------------------------------------------------

MAX_SURVEY_BUTTONS = 3
ONE_ACTIVE_SURVEY_ONLY = True
SURVEY_SEND_TO_ALL_CLIENTS = True
