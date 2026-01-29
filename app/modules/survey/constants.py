from __future__ import annotations

"""
File: app/modules/survey/constants.py
Path: app/modules/survey/constants.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Survey constants (module-authoritative).

Rules:
- Constants only
- No logic
"""

DEFAULT_SURVEY_DURATION_HOURS = 24

SURVEY_STATUS_ACTIVE = "ACTIVE"
SURVEY_STATUS_CLOSED = "CLOSED"

SURVEY_BUTTON_SETS = {
    "SENTIMENT": {
        "label": "Sentiment",
        "buttons": [
            {"id": "YES", "text": "👍 Yes", "tag": "POSITIVE"},
            {"id": "OKAY", "text": "😐 Okay", "tag": "NEUTRAL"},
            {"id": "NO", "text": "👎 No", "tag": "NEGATIVE"},
        ],
    },
    "FREQUENCY": {
        "label": "Frequency",
        "buttons": [
            {"id": "WEEKLY", "text": "Weekly", "tag": "REGULAR"},
            {"id": "OCCASIONAL", "text": "Occasionally", "tag": "OCCASIONAL"},
            {"id": "FIRST_TIME", "text": "First time", "tag": "NEW"},
        ],
    },
    "HELPFULNESS": {
        "label": "Helpfulness",
        "buttons": [
            {"id": "VERY_HELPFUL", "text": "Very helpful", "tag": "POSITIVE"},
            {"id": "SOMEWHAT_HELPFUL", "text": "Somewhat helpful", "tag": "NEUTRAL"},
            {"id": "NOT_HELPFUL", "text": "Not helpful", "tag": "NEGATIVE"},
        ],
    },
    "YES_NO_NOT_SURE": {
        "label": "Yes / No / Not Sure",
        "buttons": [
            {"id": "YES", "text": "Yes", "tag": "YES"},
            {"id": "NO", "text": "No", "tag": "NO"},
            {"id": "NOT_SURE", "text": "Not sure", "tag": "NOT_SURE"},
        ],
    },
}

SURVEY_COMMAND_DEFAULT = "SURVEY"
SURVEY_COMMAND_FREQUENCY = "SURVEY[FREQUENCY]"
SURVEY_COMMAND_HELPFULNESS = "SURVEY[HELPFULNESS]"
SURVEY_COMMAND_END = "END SURVEY"

SUPPORTED_SURVEY_COMMANDS = {
    SURVEY_COMMAND_DEFAULT: "SENTIMENT",
    SURVEY_COMMAND_FREQUENCY: "FREQUENCY",
    SURVEY_COMMAND_HELPFULNESS: "HELPFULNESS",
}

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
    "📊 Survey completed (24 hours)\n\n"
    "Question:\n"
    "{question}\n\n"
    "Responses ({total} total):\n"
    "{results}\n\n"
    "Tags updated:\n"
    "{tags}"
)

CUSTOMER_SURVEY_INTRO_TEMPLATE = (
    "🗳️ Quick question\n\n"
    "{question}\n\n"
    "Tap one option below 👇"
)

CUSTOMER_SURVEY_THANK_YOU_TEMPLATE = "Thanks for your feedback 👍"

MAX_SURVEY_BUTTONS = 3
ONE_ACTIVE_SURVEY_ONLY = True
SURVEY_SEND_TO_ALL_CLIENTS = True
