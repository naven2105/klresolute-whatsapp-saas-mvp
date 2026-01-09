"""
File: app/survey/survey_models.py

Survey database models for KLResolute MVP
-----------------------------------------
Tier: 1
Purpose:
- Survey definition
- Survey responses
- Enforce single response per client per survey
"""

from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db import Base


class Survey(Base):
    __tablename__ = "surveys"

    id = Column(Integer, primary_key=True)
    business_number = Column(String, nullable=False, index=True)
    question = Column(String, nullable=False)
    button_set = Column(String, nullable=False)

    status = Column(String, nullable=False)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    ends_at = Column(DateTime, nullable=False)
    closed_at = Column(DateTime, nullable=True)

    responses = relationship(
        "SurveyResponse",
        back_populates="survey",
        cascade="all, delete-orphan",
    )


class SurveyResponse(Base):
    __tablename__ = "survey_responses"

    id = Column(Integer, primary_key=True)

    survey_id = Column(
        Integer,
        ForeignKey("surveys.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    client_number = Column(String, nullable=False)
    button_id = Column(String, nullable=False)
    tag = Column(String, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    survey = relationship(
        "Survey",
        back_populates="responses",
    )

    __table_args__ = (
        UniqueConstraint(
            "survey_id",
            "client_number",
            name="uq_survey_response_once_per_client",
        ),
    )
