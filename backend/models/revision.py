# backend/models/revision.py
#
# WHAT: A Revision is a scheduled review session for a specific Topic.
# WHY IT EXISTS: The core of "revision debt" — one of the most important
#   signals the AI agent uses. If a topic hasn't been revised in 2 weeks,
#   the agent should prioritize it regardless of how well it was originally learned.
#
# DATA FLOW: User logs a revision → AI agent calls get_upcoming_revisions()
#   → agent sees overdue topics → agent adds them to the generated plan.
#
# DB CONCEPT: This table acts as a lightweight scheduler. We intentionally
#   avoid building a full calendar system — just: topic + planned_date + done?
#   The agent handles the "when should I revise?" question, not the schema.

import enum
from datetime import datetime, date
from typing import Optional
from sqlalchemy import String, Text, Date, DateTime, ForeignKey, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from backend.database.base import Base


class RevisionStatus(str, enum.Enum):
    PENDING   = "PENDING"   # Scheduled but not yet done
    COMPLETED = "COMPLETED" # Done
    SKIPPED   = "SKIPPED"   # User decided to skip this one


class Revision(Base):
    """
    A scheduled (or completed) revision session for a Topic.

    Key fields for the AI agent:
        topic_id       → which topic needs revision
        planned_date   → when it was supposed to happen
        status         → PENDING (overdue?) / COMPLETED / SKIPPED
        completed_date → when it actually happened

    The agent computes "revision debt" by finding:
        Revisions WHERE status=PENDING AND planned_date < today

    Database table: revisions
    """
    __tablename__ = "revisions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    planned_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="Date when revision is scheduled"
    )
    status: Mapped[str] = mapped_column(
        String(15),
        nullable=False,
        default=RevisionStatus.PENDING.value,
    )

    # Set when the user marks the revision as completed
    completed_date: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True
    )
    duration_minutes: Mapped[Optional[int]] = mapped_column(
        SmallInteger,
        nullable=True,
        comment="How long the revision took (self-reported)"
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="What the user reviewed or struggled with"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="revisions")
    topic: Mapped["Topic"] = relationship("Topic", back_populates="revisions")

    def __repr__(self) -> str:
        return (
            f"<Revision id={self.id} topic_id={self.topic_id} "
            f"planned={self.planned_date} status={self.status}>"
        )
