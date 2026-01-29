from __future__ import annotations

"""
File: app/modules/survey/__init__.py
Path: app/modules/survey/__init__.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Survey module public interface.

Only re-export stable entry points.
Do NOT add logic here.
"""

# ---- Core handlers ----
from app.modules.survey.handler import handle

# ---- Lifecycle helpers (used by jobs / admin) ----
from app.modules.survey.close_survey import close_survey_and_notify
from app.modules.survey.summary import build_survey_summary_text

# ---- ORM models ----
from app.modules.survey.models import Survey, SurveyResponse
