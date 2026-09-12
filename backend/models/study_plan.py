# backend/models/study_plan.py
#
# WHAT: Database models for AI-generated study plans.
# WHY TWO TABLES:
#   StudyPlan  = the overall plan (title, duration, owner)
#   StudyTask  = individual tasks within the plan (one per study item)
#
#   This is a one-to-many relationship: one plan has many tasks.
#   Keeping them separate allows:
#   - Querying all tasks for a specific day
#   - Marking individual tasks as completed
#   - Aggregating time estimates per day
#   - The agent to update task status later (Stage 3)
#
# DB CONCEPT: Why not store tasks as a JSON blob in the plan row?
#   JSON blobs cannot be queried efficiently. If you store tasks as JSON,
#   you cannot do: SELECT * FROM tasks WHERE day_number=3 AND status=PENDING.
#   Normalizing to a separate table keeps the database relational.

import enum
from datetime import datetime, date
from typing import TYPE_CHECKING, Optional
from sqlalchemy import String, Text, Integer, SmallInteger, Boolean, Date, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from backend.database.base import Base

if TYPE_CHECKING:
    from backend.models.user import User


class PlanStatus(str, enum.Enum):
    ACTIVE    = "ACTIVE"     # Plan is in progress
    COMPLETED = "COMPLETED"  # All tasks done
    ABANDONED = "ABANDONED"  # User dropped the plan
    DRAFT     = "DRAFT"      # Generated but not confirmed


class TaskPriority(str, enum.Enum):
    HIGH   = "HIGH"
    MEDIUM = "MEDIUM"
    LOW    = "LOW"


class TaskStatus(str, enum.Enum):
    PENDING   = "PENDING"
    COMPLETED = "COMPLETED"
    SKIPPED   = "SKIPPED"


class StudyPlan(Base):
    """
    An AI-generated study plan for a user.

    Created by the create_study_plan() tool when the agent generates a plan.
    One plan covers a fixed duration (e.g. 7 days) with a daily hours target.

    Database table: study_plans
    """
    __tablename__ = "study_plans"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Optional link to a Goal — the plan serves this goal
    goal_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("goals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    duration_days: Mapped[int] = mapped_column(
        SmallInteger, nullable=False,
        comment="Total days the plan covers"
    )
    daily_hours: Mapped[float] = mapped_column(
        nullable=False,
        comment="Target study hours per day"
    )

    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(15), nullable=False,
        default=PlanStatus.ACTIVE.value,
    )

    # Raw JSON of the LLM reasoning (for debugging and learning purposes)
    # Storing this lets you inspect exactly what the LLM produced before validation
    llm_reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="study_plans")
    tasks: Mapped[list["StudyTask"]] = relationship(
        "StudyTask",
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="StudyTask.day_number, StudyTask.id",
    )

    def __repr__(self) -> str:
        return f"<StudyPlan id={self.id} title={self.title!r} user_id={self.user_id}>"


class StudyTask(Base):
    """
    A single study task within a StudyPlan.

    Each task represents one focused study item on a specific day.
    Examples: "Practice BFS traversal", "Solve 3 DP problems", "Revise OS scheduling"

    Database table: study_tasks
    """
    __tablename__ = "study_tasks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    plan_id: Mapped[int] = mapped_column(
        ForeignKey("study_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Optional link to a specific topic
    topic_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("topics.id", ondelete="SET NULL"),
        nullable=True,
    )

    day_number: Mapped[int] = mapped_column(
        SmallInteger, nullable=False,
        comment="Which day of the plan (1-indexed)"
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    estimated_minutes: Mapped[int] = mapped_column(
        SmallInteger, nullable=False,
        comment="Estimated time to complete in minutes"
    )
    priority: Mapped[str] = mapped_column(
        String(10), nullable=False,
        default=TaskPriority.MEDIUM.value,
    )
    status: Mapped[str] = mapped_column(
        String(15), nullable=False,
        default=TaskStatus.PENDING.value,
    )

    # back-reference to plan
    plan: Mapped["StudyPlan"] = relationship("StudyPlan", back_populates="tasks")

    def __repr__(self) -> str:
        return (
            f"<StudyTask id={self.id} day={self.day_number} "
            f"title={self.title!r} plan_id={self.plan_id}>"
        )
