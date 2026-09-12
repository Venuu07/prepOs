# backend/schemas/study_plan.py
#
# WHAT: Pydantic schemas for StudyPlan and StudyTask.
#
# TWO SETS OF SCHEMAS:
#
# 1. LLM-facing schemas (prefix: LLM*)
#    These are what we expect the LLM to provide via the create_study_plan tool.
#    They are deliberately flexible (e.g. topic_id is optional).
#    We validate them before writing to the DB.
#
# 2. DB-facing schemas (Response*)
#    These represent what is stored in the database.
#    Used in API responses and for reading back plans.
#
# WHY SEPARATE?
#    The LLM might not know topic IDs. The DB needs valid FKs.
#    The LLM schemas are "raw input"; the DB schemas are "confirmed output."

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator


# =============================================================================
# LLM-FACING SCHEMAS
# What the LLM provides to the create_study_plan tool.
# Validated by plan_validator.py before DB write.
# =============================================================================

class LLMStudyTask(BaseModel):
    """One study task as provided by the LLM."""
    title: str = Field(..., min_length=1, max_length=500)
    estimated_minutes: int = Field(..., ge=5, le=480)
    priority: str = Field(default="MEDIUM", pattern="^(HIGH|MEDIUM|LOW)$")
    topic_id: Optional[int] = None
    description: Optional[str] = None


class LLMStudyDay(BaseModel):
    """One day in the plan as provided by the LLM."""
    day_number: int = Field(..., ge=1, le=365)
    focus: str = Field(..., min_length=1, max_length=200)
    tasks: list[LLMStudyTask] = Field(..., min_length=1)


class LLMStudyPlan(BaseModel):
    """
    The complete plan as provided by the LLM to create_study_plan().

    This is the structured output from the LLM.
    It goes through plan_validator.py before touching the database.
    """
    title: str = Field(..., min_length=1, max_length=300)
    duration_days: int = Field(..., ge=1, le=365)
    daily_hours: float = Field(..., ge=0.5, le=16.0)
    goal_id: Optional[int] = None
    start_date: Optional[date] = None
    description: Optional[str] = None
    days: list[LLMStudyDay] = Field(..., min_length=1)

    @field_validator("days")
    @classmethod
    def days_must_match_duration(cls, days: list, info) -> list:
        # Soft check: days list should not exceed duration_days
        # We allow FEWER days (plan can be partial) but not MORE
        duration = info.data.get("duration_days", 365)
        for day in days:
            if day.day_number > duration:
                raise ValueError(
                    f"day_number {day.day_number} exceeds duration_days {duration}"
                )
        return days


# =============================================================================
# DB / API RESPONSE SCHEMAS
# =============================================================================

class StudyTaskResponse(BaseModel):
    id: int
    plan_id: int
    day_number: int
    title: str
    estimated_minutes: int
    priority: str
    status: str
    topic_id: Optional[int]
    description: Optional[str]

    model_config = {"from_attributes": True}


class StudyPlanResponse(BaseModel):
    id: int
    user_id: int
    title: str
    duration_days: int
    daily_hours: float
    status: str
    goal_id: Optional[int]
    start_date: Optional[date]
    description: Optional[str]
    created_at: datetime
    tasks: list[StudyTaskResponse] = []

    model_config = {"from_attributes": True}
