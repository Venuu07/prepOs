# backend/services/goal_service.py

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.goal import Goal
from backend.repositories.goal_repository import GoalRepository
from backend.schemas.goal import GoalCreate, GoalUpdate
from backend.core.exceptions import NotFoundError


class GoalService:

    def __init__(self, db: AsyncSession):
        self.repo = GoalRepository(db)

    async def get_goal(self, goal_id: int) -> Goal:
        goal = await self.repo.get_by_id(goal_id)
        if goal is None:
            raise NotFoundError(f"Goal with id={goal_id} not found")
        return goal

    async def list_goals(self, user_id: int) -> list[Goal]:
        return await self.repo.get_by_user(user_id)

    async def create_goal(self, data: GoalCreate) -> Goal:
        return await self.repo.create(data)

    async def update_goal(self, goal_id: int, data: GoalUpdate) -> Goal:
        goal = await self.get_goal(goal_id)
        return await self.repo.update(goal, data)

    async def delete_goal(self, goal_id: int) -> None:
        goal = await self.get_goal(goal_id)
        await self.repo.delete(goal)
