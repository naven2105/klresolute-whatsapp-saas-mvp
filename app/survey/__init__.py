"""
app/survey/__init__.py
Survey module public interface
-------------------------------
Surveys are DISABLED.
This module provides safe no-op stubs so the application can start
without any survey implementation present.

Guard rails:
- Never raise at import time
- Never write to DB
- Log clearly if survey functionality is invoked
"""

import logging

logger = logging.getLogger("survey")

# -------------------------------------------------
# Constants (disabled / safe defaults)
# -------------------------------------------------

DEFAULT_SURVEY_DURATION_HOURS = None
SURVEY_BUTTON_SETS = {}
SUPPORTED_SURVEY_COMMANDS = set()
SURVEY_COMMAND_END = None

# -------------------------------------------------
# Services (no-op, guarded)
# -------------------------------------------------

def start_survey(*args, **kwargs):
    logger.error("SURVEY_DISABLED | start_survey called")
    return None


def get_active_survey(*args, **kwargs):
    logger.debug("SURVEY_DISABLED | get_active_survey called")
    return None


def close_survey(*args, **kwargs):
    logger.error("SURVEY_DISABLED | close_survey called")
    return None


def auto_close_expired_surveys(*args, **kwargs):
    logger.debug("SURVEY_DISABLED | auto_close_expired_surveys called")
    return []


def record_response(*args, **kwargs):
    logger.error("SURVEY_DISABLED | record_response called")
    return False


def build_survey_summary_text(*args, **kwargs):
    logger.debug("SURVEY_DISABLED | build_survey_summary_text called")
    return ""

# -------------------------------------------------
# Models (disabled)
# -------------------------------------------------

Survey = None
SurveyResponse = None

__all__ = [
    # constants
    "DEFAULT_SURVEY_DURATION_HOURS",
    "SURVEY_BUTTON_SETS",
    "SUPPORTED_SURVEY_COMMANDS",
    "SURVEY_COMMAND_END",

    # services
    "start_survey",
    "get_active_survey",
    "close_survey",
    "auto_close_expired_surveys",
    "record_response",
    "build_survey_summary_text",

    # models
    "Survey",
    "SurveyResponse",
]
