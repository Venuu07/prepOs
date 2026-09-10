# backend/schemas/problem.py

from datetime import date
from typing import Optional
from pydantic import BaseModel, Field, HttpUrl


#create
class ProblemCreate(BaseModel):
    user_id: int
    topic_id: Optional[int] = None
    title: str = Field(..., min_length=1, max_length=300)
    platform: str = Field(default="LEETCODE",
                          pattern="^(LEETCODE|CODEFORCES|CODECHEF|GEEKSFORGEEKS|HACKERRANK|ATCODER|CUSTOM)$")
    platform_id: Optional[str] = Field(default=None, max_length=50)
    url: Optional[HttpUrl] = None
    difficulty: str = Field(default="MEDIUM", pattern="^(EASY|MEDIUM|HARD)$")
    tags: Optional[str] = None
    notes: Optional[str] = None


# patch update
class ProblemUpdate(BaseModel):
    topic_id: Optional[int] = None
    title: Optional[str] = Field(default=None, min_length=1, max_length=300)
    platform: Optional[str] = Field(default=None,
                                     pattern="^(LEETCODE|CODEFORCES|CODECHEF|GEEKSFORGEEKS|HACKERRANK|ATCODER|CUSTOM)$")
    url: Optional[HttpUrl] = None
    difficulty: Optional[str] = Field(default=None, pattern="^(EASY|MEDIUM|HARD)$")
    tags: Optional[str] = None
    status: Optional[str] = Field(default=None,
                                   pattern="^(NOT_STARTED|ATTEMPTED|SOLVED|REVISED|MASTERED)$")
    confidence: Optional[str] = Field(default=None, pattern="^(LOW|MEDIUM|HIGH)$")
    notes: Optional[str] = None
    solution_approach: Optional[str] = None
    last_solved_date: Optional[date] = None
    last_revised_date: Optional[date] = None
    is_active: Optional[bool] = None

#response

class ProblemResponse(BaseModel):
    id: int
    user_id: int
    topic_id: Optional[int]
    title: str
    platform: str
    platform_id: Optional[str]
    url: Optional[str]
    difficulty: str
    tags: Optional[str]
    status: str
    confidence: str
    revision_count: int
    last_solved_date: Optional[date]
    last_revised_date: Optional[date]
    notes: Optional[str]
    solution_approach: Optional[str]
    is_active: bool

    model_config = {"from_attributes": True}


# ── Problem Attempt Schemas ───────────────────────────────────────────────────

class ProblemAttemptCreate(BaseModel):
    problem_id: int
    result: str = Field(...,
                        pattern="^(SOLVED_INDEPENDENTLY|SOLVED_WITH_HINTS|PARTIALLY_SOLVED|NOT_SOLVED)$")
    time_taken_minutes: Optional[int] = Field(default=None, ge=1, le=480)
    notes: Optional[str] = None
    is_timed: bool = False


class ProblemAttemptResponse(BaseModel):
    id: int
    problem_id: int
    result: str
    time_taken_minutes: Optional[int]
    notes: Optional[str]
    is_timed: bool
    attempted_at: str  # ISO string — datetime serialized by Pydantic

    model_config = {"from_attributes": True}
