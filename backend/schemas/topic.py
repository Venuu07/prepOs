# backend/schemas/topic.py

from typing import Optional
from pydantic import BaseModel, Field, field_validator


class TopicCreate(BaseModel):
    subject_id: int
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    order_index: int = Field(default=0, ge=0)
    difficulty: str = Field(default="MEDIUM", pattern="^(EASY|MEDIUM|HARD)$")
    is_gate_relevant: bool = False
    striver_link: Optional[str] = None
    neetcode_link: Optional[str] = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()


class TopicUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    order_index: Optional[int] = Field(default=None, ge=0)
    difficulty: Optional[str] = Field(default=None, pattern="^(EASY|MEDIUM|HARD)$")
    is_gate_relevant: Optional[bool] = None
    is_active: Optional[bool] = None
    striver_link: Optional[str] = None
    neetcode_link: Optional[str] = None


class TopicResponse(BaseModel):
    id: int
    subject_id: int
    name: str
    description: Optional[str]
    order_index: int
    difficulty: str
    is_gate_relevant: bool
    is_active: bool
    striver_link: Optional[str]
    neetcode_link: Optional[str]

    model_config = {"from_attributes": True}
