from __future__ import annotations

"""
File: app/clients/galitos/survey/summary.py
Path: app/clients/galitos/survey/summary.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Build admin-facing survey summaries with counts + percentages.
"""

from sqlalchemy.orm import Session

# ---- Survey module imports (FIXED) ----
from app.clients.galitos.survey.survey_models import Survey, SurveyResponse


def build_survey_summary_text(db: Session, survey: Survey) -> str:
    """
    Build a human-readable admin summary for a closed survey.
    """

    rows = (
        db.query(SurveyResponse.button_id)
        .filter(SurveyResponse.survey_id == survey.id)
        .all()
    )

    total = len(rows)

    if total == 0:
        return (
            "📊 Survey closed\n\n"
            f"Question:\n{survey.question}\n\n"
            "No responses were received."
        )

    counts = {}
    for (button_id,) in rows:
        counts[button_id] = counts.get(button_id, 0) + 1

    lines = []
    for button_id, count in counts.items():
        pct = round((count / total) * 100)
        lines.append(f"{button_id}: {count} ({pct}%)")

    breakdown = "\n".join(lines)

    return (
        "📊 Survey closed\n\n"
        f"Question:\n{survey.question}\n\n"
        f"{breakdown}\n\n"
        f"Total responses: {total}"
    )
