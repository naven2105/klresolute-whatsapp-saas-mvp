"""
File: app/survey/__init__.py
Path: app/survey/__init__.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
LEGACY SHIM.
Keep old import paths working while the codebase migrates to app/clients/galitos/survey.
"""

from app.clients.galitos.survey.constants import (
    DEFAULT_SURVEY_DURATION_HOURS,
    SURVEY_BUTTON_SETS,
    SUPPORTED_SURVEY_COMMANDS,
    SURVEY_COMMAND_END,
)

from app.clients.galitos.survey.lifecycle import (
    start_survey,
    get_active_survey,
    close_survey,
    auto_close_expired_surveys,
    record_response,
    build_survey_summary_text,
)

from app.clients.galitos.survey.models import Survey, SurveyResponse

__all__ = [
    "DEFAULT_SURVEY_DURATION_HOURS",
    "SURVEY_BUTTON_SETS",
    "SUPPORTED_SURVEY_COMMANDS",
    "SURVEY_COMMAND_END",
    "start_survey",
    "get_active_survey",
    "close_survey",
    "auto_close_expired_surveys",
    "record_response",
    "build_survey_summary_text",
    "Survey",
    "SurveyResponse",
]
