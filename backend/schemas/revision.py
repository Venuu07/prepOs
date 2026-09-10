# backend/schemas/revision.py

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field


class RevisionCreate(BaseModel):
    user_id: int
    topic_id: int
    planned_date: date
    duration_minutes: Optional[int] = Field(default=None, ge=5, le=480)
    notes: Optional[str] = None


class RevisionUpdate(BaseModel):
    planned_date: Optional[date] = None
    status: Optional[str] = Field(default=None,
                                   pattern="^(PENDING|COMPLETED|SKIPPED)$")
    completed_date: Optional[date] = None
    duration_minutes: Optional[int] = Field(default=None, ge=5, le=480)
    notes: Optional[str] = None


class RevisionResponse(BaseModel):
    id: int
    user_id: int
    topic_id: int
    planned_date: date
    status: str
    completed_date: Optional[date]
    duration_minutes: Optional[int]
    notes: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}
