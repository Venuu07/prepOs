# backend/schemas/goal.py

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field


class GoalCreate(BaseModel):
    user_id: int
    title: str = Field(..., min_length=1, max_length=300)
    description: Optional[str] = None
    goal_type: str = Field(default="PLACEMENT",
                           pattern="^(PLACEMENT|INTERNSHIP|GATE|COMPETITIVE|SKILL_BUILDING)$")
    priority: str = Field(default="MEDIUM", pattern="^(HIGH|MEDIUM|LOW)$")
    target_date: Optional[date] = None


class GoalUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=300)
    description: Optional[str] = None
    goal_type: Optional[str] = Field(default=None,
                                      pattern="^(PLACEMENT|INTERNSHIP|GATE|COMPETITIVE|SKILL_BUILDING)$")
    status: Optional[str] = Field(default=None,
                                   pattern="^(ACTIVE|ACHIEVED|PAUSED|ABANDONED)$")
    priority: Optional[str] = Field(default=None, pattern="^(HIGH|MEDIUM|LOW)$")
    target_date: Optional[date] = None


class GoalResponse(BaseModel):
    id: int
    user_id: int
    title: str
    description: Optional[str]
    goal_type: str
    status: str
    priority: str
    target_date: Optional[date]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
