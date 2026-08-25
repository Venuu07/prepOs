# backend/models/subject.py
#
# CONCEPT: The Subject → Topic hierarchy
#
# In PrepOS, knowledge is structured as:
#   Subject (e.g., "Operating Systems")
#   └── Topic (e.g., "CPU Scheduling", "Deadlocks")
#       └── Problems (practice questions for that topic)
#
# This is a 3-level hierarchy. Why model it this way (not flat)?
# Because it lets us:
#   - Track mastery at EACH level (not just per problem)
#   - Show "You're 60% done with OS" (subject-level analytics)
#   - Show "Your CPU Scheduling is weak" (topic-level analytics)
#   - Recommend "Solve more DP problems" (problem-level guidance)
#
# CONCEPT: Self-referential relationships (NOT used here, but worth knowing)
# Sometimes topics have sub-topics (e.g., "Graphs" → "BFS", "DFS", "Dijkstra").
# You'd model this as a self-referential relationship:
#   parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("topics.id"))
# We'll add this if needed. For now, 2-level (Subject → Topic) is sufficient.

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from backend.database.base import Base


class Subject(Base):
    """
    A top-level academic subject.

    Examples: Operating Systems, DBMS, Computer Networks,
              DSA, Object-Oriented Programming, GATE Mathematics

    This is a GLOBAL entity — not user-specific.
    All users see the same subjects.
    User-specific progress is tracked separately (in user_skills / topics).

    Database table: subjects
    """
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ── Identity ─────────────────────────────────────────────────────────────
    name: Mapped[str] = mapped_column(
        String(200),
        unique=True,
        nullable=False,
        index=True,
        comment="Subject name, e.g. 'Operating Systems'"
    )
    short_code: Mapped[Optional[str]] = mapped_column(
        String(20),
        unique=True,
        nullable=True,
        comment="Short identifier, e.g. 'OS', 'DBMS', 'CN', 'DSA'"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="What this subject covers"
    )

    # ── Metadata ─────────────────────────────────────────────────────────────
    # is_active lets us "soft disable" subjects without deleting them.
    # For example, if a subject becomes irrelevant for current placements.
    is_active: Mapped[bool] = mapped_column(
        default=True,
        server_default="true",
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    # A Subject contains many Topics.
    # "cascade all, delete-orphan" means deleting a Subject deletes all its Topics.
    # This makes sense — you can't have an OS topic with no parent subject.
    topics: Mapped[list["Topic"]] = relationship(
        "Topic",
        back_populates="subject",
        cascade="all, delete-orphan",
        order_by="Topic.order_index",
    )

    def __repr__(self) -> str:
        return f"<Subject id={self.id} name={self.name!r}>"
