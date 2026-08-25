# backend/models/__init__.py
#
# CONCEPT: Why does this file exist?
#
# Python treats any directory with an __init__.py as a "package."
# Without this file, `from backend.models.user import User` would fail.
#
# Additionally, we import ALL models here. This is critical for Alembic:
# Alembic needs to "see" every model class so it can compare them to
# the database schema and generate the correct migration.
#
# If you create a new model file, add it to this import list.
# If you forget, Alembic won't know the table exists → no migration generated.

from backend.models.user import User
from backend.models.subject import Subject
from backend.models.topic import Topic
from backend.models.problem import Problem, ProblemAttempt

__all__ = [
    "User",
    "Subject",
    "Topic",
    "Problem",
    "ProblemAttempt",
]
