"""
app/survey/__init__.py
Survey module public interface
-------------------------------
Exposes survey lifecycle services.
All imports are guarded to prevent startup failure.
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
        "SURVEY_CONSTANTS_MISSING | err=%s",
        exc,
    )
    DEFAULT_SURVEY_DURATION_HOURS = None
    SURVEY_BUTTON_SETS = {}
    SUPPORTED_SURVEY_COMMANDS = set()
    SURVEY_COMMAND_END = None

# -------------------------------------------------
# Optional services (guarded)
# -------------------------------------------------

try:
    from app.survey.survey_service import (
        start_survey,
        get_active_survey,
        close_survey,
        auto_close_expired_surveys,
        record_response,
        build_survey_summary_text,
    )
except ModuleNotFoundError as exc:
    logger.warning(
        "SURVEY_SERVICE_MISSING | err=%s",
        exc,
    )

    def start_survey(*args, **kwargs):
        logger.error("SURVEY_START_CALLED_BUT_SERVICE_MISSING")

    def get_active_survey(*args, **kwargs):
        return None

    def close_survey(*args, **kwargs):
        logger.error("SURVEY_CLOSE_CALLED_BUT_SERVICE_MISSING")

    def auto_close_expired_surveys(*args, **kwargs):
        return []

    def record_response(*args, **kwargs):
        return False

    def build_survey_summary_text(*args, **kwargs):
        return ""

# -------------------------------------------------
# Optional models (guarded)
# -------------------------------------------------

try:
    from app.survey.survey_models import (
        Survey,
        SurveyResponse,
    )
except ModuleNotFoundError as exc:
    logger.warning(
        "SURVEY_MODELS_MISSING | err=%s",
        exc,
    )
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
