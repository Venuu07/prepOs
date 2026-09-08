# backend/models/problem.py
#
# CONCEPT: The DSA Problem — The Core Tracking Unit
#
# This is the heart of the DSA tracker. Each Problem record represents
# ONE DSA problem (like "Two Sum" or "Trapping Rain Water") being tracked
# by ONE user. 
#
# KEY DESIGN: Problem is USER-SPECIFIC.
# Two users tracking the same LeetCode problem get two separate Problem records.
# This is intentional: each user has their own solve status, confidence,
# notes, and attempt history.
#
# CONCEPT: Status Enums (State Machine)
# ProblemStatus values form a progression:
#   NOT_STARTED → ATTEMPTED → SOLVED → REVISED → MASTERED
# The analytics engine uses these states to calculate:
#   - Completion rate (SOLVED + REVISED + MASTERED / total)
#   - Revision debt (SOLVED but not REVISED in 30+ days)
#   - Mastery rate (MASTERED / total)
#
# CONCEPT: Confidence vs Status
# These are different dimensions:
#   Status = "Did I solve it?" → SOLVED/NOT_STARTED/etc.
#   Confidence = "How well do I KNOW it?" → LOW/MEDIUM/HIGH
# A problem can be SOLVED but confidence=LOW (you needed hints).
# A MASTERED problem should have confidence=HIGH.
# This separation lets the analytics engine detect "weak solved problems."
#
# CONCEPT: Soft Delete
# We don't DELETE problem records. We set is_active=False.
# Why? Because ProblemAttempt records reference Problem. Deleting the problem
# would orphan the attempts (or cascade-delete valuable history).
# "Soft delete" preserves history while hiding the problem from UI.
#
# CONCEPT: The Attempts Table (ProblemAttempt)
# Why store attempts separately?
# Each attempt is a discrete event (datetime, time taken, approach, result).
# If we stored this in the Problem table, we'd need JSON blobs or multiple
# columns for "attempt1_date, attempt1_result, attempt2_date..." — ugly.
# A separate table lets us: query "all failed attempts in the last week",
# "average time to solve by difficulty", "most-reattempted problems", etc.

import enum
from datetime import datetime, date
from typing import Optional
# pyrefly: ignore [missing-import]
from sqlalchemy import (
    String, Text, DateTime, Date, ForeignKey,
    Integer, Boolean, SmallInteger
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from backend.database.base import Base


class ProblemStatus(str, enum.Enum):
    """
    Tracks where in the study lifecycle a problem currently sits.
    These form a forward progression (though users can move back e.g. to ATTEMPTED).
    """
    NOT_STARTED = "NOT_STARTED"
    ATTEMPTED   = "ATTEMPTED"   # Tried but not fully solved
    SOLVED      = "SOLVED"      # Solved (may have needed hints)
    REVISED     = "REVISED"     # Solved before AND went back to revise
    MASTERED    = "MASTERED"    # Can solve confidently without hints


class Confidence(str, enum.Enum):
    """
    User's self-assessed confidence in their ability to solve this problem.
    Used by the analytics engine to detect weak areas even among "solved" problems.
    """
    LOW    = "LOW"
    MEDIUM = "MEDIUM"
    HIGH   = "HIGH"


class Difficulty(str, enum.Enum):
    """Standard DSA problem difficulty (mirrors LeetCode/Codeforces ratings)."""
    EASY   = "EASY"
    MEDIUM = "MEDIUM"
    HARD   = "HARD"


class Platform(str, enum.Enum):
    """Which platform this problem comes from."""
    LEETCODE     = "LEETCODE"
    CODEFORCES   = "CODEFORCES"
    CODECHEF     = "CODECHEF"
    GEEKSFORGEEKS = "GEEKSFORGEEKS"
    HACKERRANK   = "HACKERRANK"
    ATCODER      = "ATCODER"
    CUSTOM       = "CUSTOM"   # User-created or offline problem


class Problem(Base):
    """
    A DSA problem tracked by a specific user.

    This table is the core of the DSA tracker.
    Each row = one user tracking one problem.

    Analytics computed from this table:
    - Topic-level mastery (avg confidence per topic)
    - Revision debt (SOLVED/REVISED but not touched in 30+ days)
    - Weak areas (low confidence + low solve rate topics)
    - Problem velocity (solved per week)

    Database table: problems
    """
    __tablename__ = "problems"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ── Ownership ─────────────────────────────────────────────────────────────
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Which user is tracking this problem"
    )
    
    topic_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("topics.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="DSA topic this problem belongs to (nullable — user may not categorize)"
    )
    # ondelete="SET NULL" on topic_id means: if the topic is deleted,
    # set topic_id to NULL rather than deleting the problem.
    # The problem still exists — it's just uncategorized.

    # ── Problem Identity ──────────────────────────────────────────────────────
    title: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
        index=True,
        comment="Problem title, e.g. 'Trapping Rain Water'"
    )
    platform: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=Platform.LEETCODE.value,
        comment="Source platform: LEETCODE, CODEFORCES, etc."
    )
    platform_id: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Platform-specific ID (e.g., LeetCode problem number '42')"
    )
    url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Direct URL to the problem"
    )

    # ── Categorization ────────────────────────────────────────────────────────
    difficulty: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default=Difficulty.MEDIUM.value,
        comment="EASY, MEDIUM, or HARD"
    )
    # tags stores comma-separated tags like "arrays,two-pointers,sliding-window"
    # Why not a separate tags table? For now, simple string is fine.
    # We'd normalize this to a proper many-to-many if we needed to query by tag.
    tags: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Comma-separated topic tags from the platform"
    )

    # ── User's Progress State ─────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(15),
        nullable=False,
        default=ProblemStatus.NOT_STARTED.value,
        comment="Current state in the solve lifecycle"
    )
    confidence: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default=Confidence.LOW.value,
        comment="User's self-assessed confidence level"
    )

    # ── Revision Tracking ─────────────────────────────────────────────────────
    # These are used by the Revision Debt analytics.
    # "Revision debt" = problems that haven't been revisited in 30+ days.
    revision_count: Mapped[int] = mapped_column(
        SmallInteger,
        default=0,
        nullable=False,
        comment="Number of times the user has deliberately revised this problem"
    )
    last_solved_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="When the user last solved/attempted this problem"
    )
    last_revised_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="When the user last went back to revise this problem"
    )

    # ── Notes ─────────────────────────────────────────────────────────────────
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="User's personal notes: approach, key insights, gotchas"
    )
    solution_approach: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="High-level description of the approach/algorithm used"
    )

    # ── Soft Delete ───────────────────────────────────────────────────────────
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
        comment="False = soft deleted. Preserves attempt history."
    )

    # ── Timestamps ───────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="problems")
    topic: Mapped[Optional["Topic"]] = relationship("Topic", back_populates="problems")
    attempts: Mapped[list["ProblemAttempt"]] = relationship(
        "ProblemAttempt",
        back_populates="problem",
        cascade="all, delete-orphan",
        order_by="ProblemAttempt.attempted_at.desc()",
    )

    def __repr__(self) -> str:
        return (
            f"<Problem id={self.id} title={self.title!r} "
            f"status={self.status} user_id={self.user_id}>"
        )


class AttemptResult(str, enum.Enum):
    """Outcome of a single problem attempt."""
    SOLVED_INDEPENDENTLY = "SOLVED_INDEPENDENTLY"  # No hints, clean solution
    SOLVED_WITH_HINTS    = "SOLVED_WITH_HINTS"      # Needed to look at hints
    PARTIALLY_SOLVED     = "PARTIALLY_SOLVED"       # Got some cases, not all
    NOT_SOLVED           = "NOT_SOLVED"             # Couldn't solve it


class ProblemAttempt(Base):
    """
    A single attempt at a problem.

    Why a separate table?
    - Each attempt is a timestamped event with its own metadata.
    - You want to query: "How many times did I fail Graph problems this week?"
    - You want to track improvement: attempt 1 = NOT_SOLVED, attempt 3 = SOLVED
    - Without this table, you lose all historical attempt data.

    Database table: problem_attempts
    """
    __tablename__ = "problem_attempts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    problem_id: Mapped[int] = mapped_column(
        ForeignKey("problems.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Which problem was attempted"
    )

    # ── Attempt Data ──────────────────────────────────────────────────────────
    result: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="Outcome of this attempt"
    )
    time_taken_minutes: Mapped[Optional[int]] = mapped_column(
        SmallInteger,
        nullable=True,
        comment="How many minutes it took to attempt (self-reported)"
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="What approach was tried, what didn't work, key learnings"
    )
    is_timed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Was this a timed/mock interview attempt?"
    )

    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
        comment="When this attempt occurred"
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    problem: Mapped["Problem"] = relationship("Problem", back_populates="attempts")

    def __repr__(self) -> str:
        return (
            f"<ProblemAttempt id={self.id} problem_id={self.problem_id} "
            f"result={self.result} at={self.attempted_at}>"
        )
