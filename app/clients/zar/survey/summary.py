# ==================================================
# File: summary.py
# Path: app/clients/zar/survey/summary.py
# Project: KLResolute WhatsApp SaaS MVP
#
# Purpose:
# Build formatted survey results summary.
#
# Rules:
# - Tenant isolated
# - Read-only DB access
# - No messaging logic
# ==================================================

from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy import text


def build_survey_summary_text(
    *,
    db: Session,
    survey_id: str,
    question: str,
) -> str:

    rows = (
        db.execute(
            text(
                """
                SELECT button_id, COUNT(*) AS votes
                FROM r_zar__survey_responses
                WHERE survey_id = :survey_id
                GROUP BY button_id
                """
            ),
            {"survey_id": survey_id},
        )
        .mappings()
        .all()
    )

    vote_map = {
        "positive": 0,
        "neutral": 0,
        "negative": 0,
    }

    for r in rows:
        key = (r.get("button_id") or "").lower()
        if key in vote_map:
            vote_map[key] = r.get("votes", 0)

    total = sum(vote_map.values())

    summary = (
        "📊 Survey Results\n\n"
        "Question:\n"
        f"{question}\n\n"
        "Responses:\n"
        f"👍 Positive: {vote_map['positive']}\n"
        f"😐 Neutral: {vote_map['neutral']}\n"
        f"👎 Negative: {vote_map['negative']}\n\n"
        f"Total responses: {total}"
    )

    return summary