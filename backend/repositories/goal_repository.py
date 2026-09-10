# backend/repositories/goal_repository.py

from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.goal import Goal
from backend.schemas.goal import GoalCreate, GoalUpdate


class GoalRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, goal_id: int) -> Optional[Goal]:
        result = await self.db.execute(select(Goal).where(Goal.id == goal_id))
        return result.scalar_one_or_none()

    async def get_by_user(self, user_id: int) -> list[Goal]:
        # Returns active goals first, then by target_date ascending (soonest deadline first)
        result = await self.db.execute(
            select(Goal)
            .where(Goal.user_id == user_id)
            .order_by(Goal.status, Goal.target_date.asc().nulls_last())
        )
        return list(result.scalars().all())

    async def create(self, data: GoalCreate) -> Goal:
        goal = Goal(**data.model_dump())
        self.db.add(goal)
        await self.db.flush()
        await self.db.refresh(goal)
        return goal

    async def update(self, goal: Goal, data: GoalUpdate) -> Goal:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(goal, field, value)
        await self.db.flush()
        await self.db.refresh(goal)
        return goal

    async def delete(self, goal: Goal) -> None:
        await self.db.delete(goal)
        await self.db.flush()
