# backend/database/base.py
#
# CONCEPT: SQLAlchemy Declarative Base
#
# SQLAlchemy's ORM works through a "declarative" system.
# You define Python classes, and SQLAlchemy generates the corresponding
# SQL (CREATE TABLE, SELECT, INSERT, etc.) from those class definitions.
#
# The "Base" is the parent class that every model inherits from.
# When you inherit from Base:
#   1. SQLAlchemy registers your class in its internal metadata registry.
#   2. Your class gains ORM capabilities (query, save, delete, relationships).
#   3. Alembic can inspect Base.metadata to auto-generate migrations.
#
# IMPORTANT: All models must be imported before Alembic can see them.
# We handle that in the env.py file.
#
# DeclarativeBase (SQLAlchemy 2.0+) vs the old declarative_base():
# SQLAlchemy 2.0 introduced a class-based approach (DeclarativeBase).
# It's type-safe and works better with modern Python type checkers.
# The old approach was:  Base = declarative_base()
# The new approach is:  class Base(DeclarativeBase): pass
# Both do the same thing — new syntax is just more Pythonic.

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    The base class that all PrepOS SQLAlchemy models inherit from.

    Inheriting from this class gives a Python class:
    - A __tablename__ (if you define it)
    - Column mapping (via Mapped[] type annotations)
    - Relationship support (via relationship())
    - Automatic registration in Base.metadata

    Usage:
        class User(Base):
            __tablename__ = "users"
            id: Mapped[int] = mapped_column(primary_key=True)
    """
    pass
