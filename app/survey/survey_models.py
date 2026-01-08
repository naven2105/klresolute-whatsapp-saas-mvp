"""
app/survey/survey_models.py

Survey data models for KLResolute MVP
------------------------------------
Scope: Tier 1 only
Purpose: Persist surveys and survey responses
Rules:
- One active survey per business
- One response per client per survey
- No logic beyond structure
"""

from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base  # adjust import if your Base lives elsewhere
from app.survey.survey_constants import (
    SURVEY_STATUS_ACTIVE,
    SURVEY_STATUS_CLOSED,
)


class Survey(Base):
    __tablename__ = "surveys"

    id = Column(Integer, primary_key=True, index=True)

    business_number = Column(String, index=True, nullable=False)
    question = Column(String, nullable=False)

    button_set = Column(String, nullable=False)  # SENTIMENT | FREQUENCY | HELPFULNESS
    status = Column(String, default=SURVEY_STATUS_ACTIVE, nullable=False)

    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ends_at = Column(DateTime, nullable=False)
    closed_at = Column(DateTime, nullable=True)

    responses = relationship(
        "SurveyResponse",
        back_populates="survey",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        # Enforce only one ACTIVE survey per business
        UniqueConstraint(
            "business_number",
            "status",
            name="uq_active_survey_per_business",
        ),
    )

    def __repr__(self) -> str:
        return f"<Survey id={self.id} status={self.status} question='{self.question[:30]}'>"


class SurveyResponse(Base):
    __tablename__ = "survey_responses"

    id = Column(Integer, primary_key=True, index=True)

    survey_id = Column(Integer, ForeignKey("surveys.id"), nullable=False)

    client_number = Column(String, index=True, nullable=False)
    button_id = Column(String, nullable=False)   # e.g. YES, NO, WEEKLY
    tag = Column(String, nullable=False)         # POSITIVE, REGULAR, etc.

    responded_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    survey = relationship("Survey", back_populates="responses")

    __table_args__ = (
        # One response per client per survey
        UniqueConstraint(
            "survey_id",
            "client_number",
            name="uq_one_response_per_client_per_survey",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<SurveyResponse survey_id={self.survey_id} "
            f"client={self.client_number} button={self.button_id}>"
        )
