# backend/models/topic.py
#
# CONCEPT: Topic — The User-Specific Preparation Unit
#
# Topics are where user-specific mastery tracking happens.
# A Topic belongs to a Subject, and each user tracks their progress per-topic.
#
# Key design question: Do we store user progress IN the topic table, or separate?
#
# We store it SEPARATE, in a "user_topic_progress" table (to be added later).
# Why? Because Topic is a global entity (OS → Deadlocks is the same for everyone).
# User progress is user-specific. Mixing them would mean we can't have a
# single "Deadlocks" record — we'd need one per user.
#
# For this phase, we keep Topic simple:
#   - Global topic definition (name, what it covers, which subject it belongs to)
#   - A suggested order within the subject
#   - Difficulty metadata
#
# CONCEPT: ForeignKey
# ForeignKey("subjects.id") creates a DB-level constraint that ensures:
#   - Every topic's subject_id must reference an EXISTING subject
#   - You can't delete a subject that has topics (without cascading)
#   - PostgreSQL enforces this — not just the ORM
#
# The string format is "tablename.columnname".
# NOT "ClassName.attribute_name" — SQLAlchemy uses the ACTUAL table names.

import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, DateTime, ForeignKey, Integer, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from backend.database.base import Base


class TopicDifficulty(str, enum.Enum):
    """
    Overall difficulty rating for a topic — not per-user, but as a general guide.
    EASY:   Students usually master this quickly (e.g., Arrays basics)
    MEDIUM: Requires effort (e.g., BFS/DFS)
    HARD:   Advanced topics (e.g., Segment Trees, NP-completeness)
    """
    EASY   = "EASY"
    MEDIUM = "MEDIUM"
    HARD   = "HARD"


class Topic(Base):
    """
    A specific topic within a subject.

    Examples:
        OS       → CPU Scheduling, Deadlocks, Memory Management
        DSA      → Arrays, Linked Lists, Binary Search, Graphs
        DBMS     → Normalization, Transactions, Indexing
        Networks → TCP/IP, HTTP, DNS, Routing

    Topics are global — same topic for all users.
    User-specific state (MASTERED, WEAK, etc.) is tracked in user_topic_progress.

    Database table: topics
    """
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ── Foreign Key to Subject ────────────────────────────────────────────────
    # This column stores the ID of the parent subject.
    # ForeignKey creates the DB constraint. relationship() creates the ORM link.
    # ondelete="CASCADE" means: if the subject is deleted, delete this topic too.
    # This mirrors the cascade on the relationship() in Subject.
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Which subject this topic belongs to"
    )

    # ── Identity ─────────────────────────────────────────────────────────────
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True,
        comment="Topic name, e.g. 'CPU Scheduling'"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="What this topic covers and why it matters"
    )

    # ── Ordering & Metadata ───────────────────────────────────────────────────
    # order_index controls display order within a subject.
    # Example: In DSA, Arrays (1) → Linked Lists (2) → Stacks (3) → ...
    # SmallInteger: only 2 bytes (vs Integer = 4 bytes). For numbers 0-32767.
    # We only need small numbers for ordering within a subject.
    order_index: Mapped[int] = mapped_column(
        SmallInteger,
        default=0,
        nullable=False,
        comment="Display/learning order within the subject (0-indexed)"
    )
    difficulty: Mapped[str] = mapped_column(
        String(10),
        default=TopicDifficulty.MEDIUM.value,
        nullable=False,
        comment="General difficulty: EASY, MEDIUM, HARD"
    )

    # ── Content Links ─────────────────────────────────────────────────────────
    # Optional links to external resources (Striver, Neetcode, etc.)
    # We store as Text (potentially long URLs or comma-separated lists).
    striver_link: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Link to Striver's guide for this topic"
    )
    neetcode_link: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Link to NeetCode roadmap entry"
    )

    # ── Gate Relevance ────────────────────────────────────────────────────────
    # PrepOS supports GATE prep. This flag marks topics frequently tested in GATE.
    is_gate_relevant: Mapped[bool] = mapped_column(
        default=False,
        server_default="false",
        nullable=False,
        comment="Is this topic commonly tested in GATE exams?"
    )
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
    subject: Mapped["Subject"] = relationship(
        "Subject",
        back_populates="topics"
    )

    problems: Mapped[list["Problem"]] = relationship(
        "Problem",
        back_populates="topic",
        cascade="all, delete-orphan",
    )
    revisions: Mapped[list["Revision"]] = relationship(
        "Revision",
        back_populates="topic",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Topic id={self.id} name={self.name!r} subject_id={self.subject_id}>"
