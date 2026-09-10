# backend/repositories/problem_repository.py

from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.problem import Problem, ProblemAttempt
from backend.schemas.problem import ProblemCreate, ProblemUpdate, ProblemAttemptCreate


class ProblemRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, problem_id: int) -> Optional[Problem]:
        result = await self.db.execute(select(Problem).where(Problem.id == problem_id))
        return result.scalar_one_or_none()

    async def get_by_user(self, user_id: int, skip: int = 0, limit: int = 100) -> list[Problem]:
        result = await self.db.execute(
            select(Problem)
            .where(Problem.user_id == user_id, Problem.is_active == True)
            .order_by(Problem.created_at.desc())
            .offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_topic(self, topic_id: int, user_id: int) -> list[Problem]:
        result = await self.db.execute(
            select(Problem)
            .where(Problem.topic_id == topic_id, Problem.user_id == user_id,
                   Problem.is_active == True)
            .order_by(Problem.title)
        )
        return list(result.scalars().all())

    async def create(self, data: ProblemCreate) -> Problem:
        problem = Problem(**data.model_dump())
        self.db.add(problem)
        await self.db.flush()
        await self.db.refresh(problem)
        return problem

    async def update(self, problem: Problem, data: ProblemUpdate) -> Problem:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(problem, field, value)
        await self.db.flush()
        await self.db.refresh(problem)
        return problem

    async def delete(self, problem: Problem) -> None:
        # Soft delete — preserve attempt history
        problem.is_active = False
        await self.db.flush()

    # ── Attempts ─────────────────────────────────────────────────────────────

    async def create_attempt(self, data: ProblemAttemptCreate) -> ProblemAttempt:
        attempt = ProblemAttempt(**data.model_dump())
        self.db.add(attempt)
        await self.db.flush()
        await self.db.refresh(attempt)
        return attempt

    async def get_attempts(self, problem_id: int) -> list[ProblemAttempt]:
        result = await self.db.execute(
            select(ProblemAttempt)
            .where(ProblemAttempt.problem_id == problem_id)
            .order_by(ProblemAttempt.attempted_at.desc())
        )
        return list(result.scalars().all())
