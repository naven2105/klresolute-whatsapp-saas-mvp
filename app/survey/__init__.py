"""
app/survey/__init__.py
Survey module public interface
-------------------------------
Exposes survey lifecycle services.
Constants are optional and must not break app startup.
"""

import logging

logger = logging.getLogger("survey")

# -------------------------------------------------
# Optional constants (guarded)
# -------------------------------------------------

try:
    from app.survey.survey_constants import (
        DEFAULT_SURVEY_DURATION_HOURS,
        SURVEY_BUTTON_SETS,
        SUPPORTED_SURVEY_COMMANDS,
        SURVEY_COMMAND_END,
    )
except ModuleNotFoundError as exc:
    logger.warning(
        "SURVEY_CONSTANTS_MISSING | module=app.survey.survey_constants | err=%s",
        exc,
    )

    # Safe fallbacks (do NOT change behaviour, only prevent crash)
    DEFAULT_SURVEY_DURATION_HOURS = None
    SURVEY_BUTTON_SETS = {}
    SUPPORTED_SURVEY_COMMANDS = set()
    SURVEY_COMMAND_END = None

# -------------------------------------------------
# Services (required)
# -------------------------------------------------

from app.survey.survey_service import (
    start_survey,
    get_active_survey,
    close_survey,
    auto_close_expired_surveys,
    record_response,
    build_survey_summary_text,
)

# -------------------------------------------------
# Models (required)
# -------------------------------------------------

from app.survey.survey_models import (
    Survey,
    SurveyResponse,
)

__all__ = [
    # constants (may be None / empty if not present)
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
