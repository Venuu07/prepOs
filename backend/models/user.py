# backend/models/user.py
#
# CONCEPT: SQLAlchemy Model with Mapped[] Annotations (SQLAlchemy 2.0 style)
#
# Old SQLAlchemy (<2.0):
#   class User(Base):
#       id = Column(Integer, primary_key=True)
#       email = Column(String, nullable=False)
#
# New SQLAlchemy (2.0+):
#   class User(Base):
#       id: Mapped[int] = mapped_column(primary_key=True)
#       email: Mapped[str] = mapped_column(nullable=False)
#
# The new style uses Python type annotations (Mapped[int]).
# Benefits:
#   1. Type checkers (mypy, pyright) understand the types → better IDE support.
#   2. Mapped[Optional[str]] automatically sets nullable=True in the DB column.
#   3. Mapped[str] (non-optional) automatically means nullable=False.
#   4. The code reads more like regular Python, not magic Column() calls.
#
# CONCEPT: Enums in SQLAlchemy
# We define Python Enum classes and store their values as strings in PostgreSQL.
# This gives us:
#   - Type safety in Python (can only assign valid enum values)
#   - Readable values in the database ("ACTIVE" not "1")
#   - Easy validation in Pydantic schemas
#
# CONCEPT: server_default vs default
#   - default: Python-side default, computed BEFORE the SQL INSERT
#   - server_default: a SQL expression that PostgreSQL evaluates
#                     (e.g., "CURRENT_TIMESTAMP" runs in the DB itself)
# For timestamps, server_default="CURRENT_TIMESTAMP" means the DB sets the
# time — useful if your app server clock and DB clock drift differently.
# For uuid generation, we generate on the Python side (uuid4).

import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Boolean, DateTime, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from backend.database.base import Base


class UserStatus(str, enum.Enum):
    """
    Whether the user account is active or deactivated.
    str + enum.Enum means the enum VALUE is a string.
    This lets us do: UserStatus.ACTIVE == "ACTIVE" → True
    Very useful for comparisons and serialization.
    """
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class User(Base):
    """
    Represents a PrepOS user account.

    Database table: users

    DESIGN DECISIONS:
    - We use an integer surrogate key (id) as the primary key.
      Why not UUID? Integers are faster to join and index.
      We can always expose a public UUID separately if needed.
    - Passwords are stored as hashed strings (bcrypt hash). NEVER store plaintext.
    - created_at / updated_at use server_default so the DB timestamps itself.

    RELATIONSHIPS:
    A User has many:
    - Goals (their preparation targets)
    - Problems (the DSA problems they're tracking)
    - Study Sessions (time they spent studying)
    - Study Plans (AI-generated preparation schedules)
    - Agent Runs (history of AI agent interactions)

    We use relationship() to define these ORM-level connections.
    SQLAlchemy doesn't auto-fetch related objects — you must explicitly
    joinedload() or selectinload() them. This is intentional: it prevents
    accidental N+1 query problems.
    """
    __tablename__ = "users"

    # ── Primary Key ──────────────────────────────────────────────────────────
    # autoincrement=True is the default for Integer PKs — PostgreSQL uses SERIAL.
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ── Identity ─────────────────────────────────────────────────────────────
    # unique=True → PostgreSQL creates a UNIQUE INDEX on this column.
    # index=True → Creates a regular B-tree index for fast lookups by email.
    # Mapped[str] (non-Optional) → nullable=False in the DB.
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        comment="User's login email. Must be unique."
    )
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Display name"
    )

    # ── Auth ─────────────────────────────────────────────────────────────────
    # Optional[str] → nullable=True. We store the bcrypt hash, not the password.
    # Bcrypt output is always 60 chars, but String(255) gives us room.
    hashed_password: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="bcrypt hash. Never store plaintext passwords."
    )

    # ── Profile ──────────────────────────────────────────────────────────────
    # These are optional fields the user can fill in over time.
    target_role: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="E.g. 'Software Engineer', 'Data Scientist'"
    )
    target_companies: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Comma-separated list or JSON string of target companies"
    )
    graduation_year: Mapped[Optional[int]] = mapped_column(
        nullable=True,
        comment="Expected graduation year"
    )

    # ── Status ───────────────────────────────────────────────────────────────
    # SAEnum maps our Python enum to a PostgreSQL CHECK constraint.
    # native_enum=False → stores as VARCHAR, not a PostgreSQL ENUM type.
    # VARCHAR is more flexible (easier to add new values without migrations).
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
        comment="False for soft-deleted or banned accounts"
    )

    # ── Timestamps ───────────────────────────────────────────────────────────
    # func.now() is a SQLAlchemy expression for CURRENT_TIMESTAMP.
    # server_default means PostgreSQL sets this — the Python app doesn't need to.
    # onupdate=func.now() → every UPDATE statement automatically sets updated_at.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Account creation timestamp (UTC)"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Last modification timestamp (UTC)"
    )

    # ── ORM Relationships ─────────────────────────────────────────────────────
    # CONCEPT: Relationships
    # relationship() tells SQLAlchemy: "This model is connected to another model."
    # back_populates="user" means the other model has a .user attribute pointing back.
    # This is bidirectional: user.problems → list of problems, problem.user → the user.
    #
    # lazy="select" (default) means: DON'T load problems when loading a user.
    # Only fetch when you explicitly access user.problems.
    # In async code, we avoid this implicit lazy loading by using selectinload().

    problems: Mapped[list["Problem"]] = relationship(
        "Problem",
        back_populates="user",
        cascade="all, delete-orphan",
        # cascade="all, delete-orphan" means:
        #   - "all": propagate save, merge, expunge operations
        #   - "delete-orphan": if you remove a problem from user.problems,
        #     delete it from the DB (it's "orphaned" — not owned by anyone)
    )

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<User id={self.id} email={self.email!r}>"
