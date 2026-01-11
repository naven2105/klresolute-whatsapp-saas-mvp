"""
app/survey/__init__.py
Survey module public interface
-------------------------------
Exposes survey lifecycle services and constants.
Internal implementation details stay private.
"""

from app.survey.survey_constants import (
    DEFAULT_SURVEY_DURATION_HOURS,
    SURVEY_BUTTON_SETS,
    SUPPORTED_SURVEY_COMMANDS,
    SURVEY_COMMAND_END,
)

from app.survey.survey_service import (
    start_survey,
    get_active_survey,
    close_survey,
    auto_close_expired_surveys,
    record_response,
    build_survey_summary_text,
)

from app.survey.survey_models import (
    Survey,
    SurveyResponse,
)

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
