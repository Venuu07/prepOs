# backend/models/__init__.py
# All models must be imported here so Alembic can discover them.

from backend.models.user import User
from backend.models.subject import Subject
from backend.models.topic import Topic
from backend.models.problem import Problem, ProblemAttempt
from backend.models.goal import Goal
from backend.models.revision import Revision
from backend.models.study_plan import StudyPlan, StudyTask

__all__ = [
    "User",
    "Subject",
    "Topic",
    "Problem",
    "ProblemAttempt",
    "Goal",
    "Revision",
    "StudyPlan",
    "StudyTask",
]
