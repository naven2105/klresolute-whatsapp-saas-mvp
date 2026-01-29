from __future__ import annotations

"""
File: app/survey/survey_models.py
Path: app/survey/survey_models.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
LEGACY SHIM.
Re-exports module ORM models to prevent duplicate table definitions.
"""

from app.modules.survey.models import Survey, SurveyResponse

__all__ = ["Survey", "SurveyResponse"]
