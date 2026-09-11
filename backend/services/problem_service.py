# backend/services/problem_service.py
#
# WHAT: Business logic for Problems and ProblemAttempts.
# WHY: When a user logs an attempt, the service also updates the Problem's
#      status and last_solved_date — this is business logic, not the router's job.
# ONE FASTAPI CONCEPT: response_model in the router will use ProblemResponse schema
#   to serialize the SQLAlchemy object returned here.
# ONE DB CONCEPT: updated_at uses onupdate=func.now() in the model,
#   so every UPDATE automatically timestamps itself — no app code needed.

from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.problem import Problem, ProblemAttempt, ProblemStatus, Confidence
from backend.repositories.problem_repository import ProblemRepository
from backend.schemas.problem import ProblemCreate, ProblemUpdate, ProblemAttemptCreate
from backend.core.exceptions import NotFoundError


class ProblemService:

    def __init__(self, db: AsyncSession):
        self.repo = ProblemRepository(db)

    async def get_problem(self, problem_id: int) -> Problem:
        problem = await self.repo.get_by_id(problem_id)
        if problem is None:
            raise NotFoundError(f"Problem with id={problem_id} not found")
        return problem

    async def list_problems(self, user_id: int, topic_id: int | None = None,
                            skip: int = 0, limit: int = 100) -> list[Problem]:
        if topic_id is not None:
            return await self.repo.get_by_topic(topic_id, user_id)
        return await self.repo.get_by_user(user_id, skip=skip, limit=limit)

    async def create_problem(self, data: ProblemCreate) -> Problem:
        return await self.repo.create(data)

    async def update_problem(self, problem_id: int, data: ProblemUpdate) -> Problem:
        problem = await self.get_problem(problem_id)
        return await self.repo.update(problem, data)

    async def delete_problem(self, problem_id: int) -> None:
        problem = await self.get_problem(problem_id)
        await self.repo.delete(problem)

    # ── Problem Attempts ──────────────────────────────────────────────────────

    async def log_attempt(self, data: ProblemAttemptCreate) -> ProblemAttempt:
        """
        Log a new attempt and automatically update the Problem's status.
        This is the key business rule: the problem's state machine advances
        based on the attempt result.
        """
        # Verify the problem exists
        problem = await self.get_problem(data.problem_id)

        # Create the attempt record
        attempt = await self.repo.create_attempt(data)

        # Update problem status based on result
        if data.result in ("SOLVED_INDEPENDENTLY", "SOLVED_WITH_HINTS"):
            # Only upgrade status, never downgrade
            if problem.status == ProblemStatus.NOT_STARTED.value:
                problem.status = ProblemStatus.SOLVED.value
            problem.last_solved_date = date.today()
            # Upgrade confidence if solved independently
            if data.result == "SOLVED_INDEPENDENTLY":
                problem.confidence = Confidence.HIGH.value

        await self.repo.db.flush()
        return attempt

    async def get_attempts(self, problem_id: int) -> list[ProblemAttempt]:
        await self.get_problem(problem_id)  # validates existence
        return await self.repo.get_attempts(problem_id)
