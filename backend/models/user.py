# backend/models/user.py


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
    This lets us do: UserStatus.ACTIVE == "ACTIVE" â†’ True
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
    SQLAlchemy doesn't auto-fetch related objects â€” you must explicitly
    joinedload() or selectinload() them. This is intentional: it prevents
    accidental N+1 query problems.
    """
    __tablename__ = "users"

    # â”€â”€ Primary Key â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # autoincrement=True is the default for Integer PKs â€” PostgreSQL uses SERIAL.
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # â”€â”€ Identity â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # unique=True â†’ PostgreSQL creates a UNIQUE INDEX on this column.
    # index=True â†’ Creates a regular B-tree index for fast lookups by email.
    # Mapped[str] (non-Optional) â†’ nullable=False in the DB.
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

    # â”€â”€ Auth â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Optional[str] â†’ nullable=True. We store the bcrypt hash, not the password.
    # Bcrypt output is always 60 chars, but String(255) gives us room.
    hashed_password: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="bcrypt hash. Never store plaintext passwords."
    )

    # â”€â”€ Profile â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

    # â”€â”€ Status â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # SAEnum maps our Python enum to a PostgreSQL CHECK constraint.
    # native_enum=False â†’ stores as VARCHAR, not a PostgreSQL ENUM type.
    # VARCHAR is more flexible (easier to add new values without migrations).
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
        comment="False for soft-deleted or banned accounts"
    )

    # â”€â”€ Timestamps â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # func.now() is a SQLAlchemy expression for CURRENT_TIMESTAMP.
    # server_default means PostgreSQL sets this â€” the Python app doesn't need to.
    # onupdate=func.now() â†’ every UPDATE statement automatically sets updated_at.
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

    # â”€â”€ ORM Relationships â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # CONCEPT: Relationships
    # relationship() tells SQLAlchemy: "This model is connected to another model."
    # back_populates="user" means the other model has a .user attribute pointing back.
    # This is bidirectional: user.problems â†’ list of problems, problem.user â†’ the user.
    #
    # lazy="select" (default) means: DON'T load problems when loading a user.
    # Only fetch when you explicitly access user.problems.
    # In async code, we avoid this implicit lazy loading by using selectinload().

    problems: Mapped[list["Problem"]] = relationship(
        "Problem",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    goals: Mapped[list["Goal"]] = relationship(
        "Goal",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    revisions: Mapped[list["Revision"]] = relationship(
        "Revision",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    study_plans: Mapped[list["StudyPlan"]] = relationship(
        "StudyPlan",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<User id={self.id} email={self.email!r}>"

