"""
File: app/modules/survey/__init__.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Explicit public interface for Survey module.

Rules (LOCKED):
- No logic
- No side effects
- Only stable exports
"""

from app.modules.survey.handler import handle
from app.modules.survey.models import Survey, SurveyResponse

__all__ = [
    "handle",
    "Survey",
    "SurveyResponse",
]
