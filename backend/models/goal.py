# backend/models/goal.py
#
# WHAT: A Goal is a high-level preparation target set by the user.
# WHY IT EXISTS: The AI planning agent needs to understand the user's intent.
#   "Crack EPAM placement in 15 days" is fundamentally different from
#   "Prepare for GATE 2027." The agent uses goals to calibrate urgency,
#   topic selection, and time allocation.
#
# DATA FLOW: User creates a Goal → AI agent reads goals via get_user_goals()
#   tool → agent factors deadline + priority into the generated plan.
#
# FASTAPI CONCEPT: The goal_type Enum will appear as a dropdown in Swagger UI
#   automatically because Pydantic recognizes Python enums.
#
# DB CONCEPT: Date vs DateTime — target_date is a DATE (no time component).
#   A deadline is a calendar day, not a specific moment. Using Date saves
#   4 bytes per row and avoids timezone confusion.

import enum
from datetime import datetime, date
from typing import Optional
from sqlalchemy import String, Text, Date, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from backend.database.base import Base


class GoalType(str, enum.Enum):
    PLACEMENT       = "PLACEMENT"       # Campus/off-campus placements
    INTERNSHIP      = "INTERNSHIP"      # Internship roles
    GATE            = "GATE"            # GATE exam
    COMPETITIVE     = "COMPETITIVE"     # Competitive programming
    SKILL_BUILDING  = "SKILL_BUILDING"  # General learning goal


class GoalStatus(str, enum.Enum):
    ACTIVE    = "ACTIVE"    # Currently working on this
    ACHIEVED  = "ACHIEVED"  # Goal was met
    PAUSED    = "PAUSED"    # Temporarily paused
    ABANDONED = "ABANDONED" # Given up / no longer relevant


class GoalPriority(str, enum.Enum):
    HIGH   = "HIGH"
    MEDIUM = "MEDIUM"
    LOW    = "LOW"


class Goal(Base):
    """
    A user's preparation goal.

    Examples:
        "Crack EPAM SDE placement by Oct 15"
        "Complete DSA revision before college resumes"
        "GATE 2025 preparation"

    The AI planning agent uses goals as its primary input:
        goal.target_date → urgency (days remaining)
        goal.goal_type   → which topics are most relevant
        goal.priority    → how to allocate time across multiple goals

    Database table: goals
    """
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
        comment="Short goal title, e.g. 'EPAM SDE Placement'"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="More detail about the goal and success criteria"
    )
    goal_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=GoalType.PLACEMENT.value,
    )
    status: Mapped[str] = mapped_column(
        String(15),
        nullable=False,
        default=GoalStatus.ACTIVE.value,
    )
    priority: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default=GoalPriority.MEDIUM.value,
    )
    target_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Deadline for this goal"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="goals")

    def __repr__(self) -> str:
        return f"<Goal id={self.id} title={self.title!r} status={self.status}>"
