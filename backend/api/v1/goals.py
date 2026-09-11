# backend/api/v1/goals.py

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.session import get_db
from backend.services.goal_service import GoalService
from backend.schemas.goal import GoalCreate, GoalUpdate, GoalResponse

router = APIRouter()


def get_goal_service(db: AsyncSession = Depends(get_db)) -> GoalService:
    return GoalService(db)


@router.post("/", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
async def create_goal(
    body: GoalCreate,
    service: GoalService = Depends(get_goal_service),
):
    """Create a new preparation goal."""
    return await service.create_goal(body)


@router.get("/", response_model=list[GoalResponse])
async def list_goals(
    user_id: int,
    service: GoalService = Depends(get_goal_service),
):
    """List all goals for a user, ordered by urgency (soonest deadline first)."""
    return await service.list_goals(user_id)


@router.get("/{goal_id}", response_model=GoalResponse)
async def get_goal(
    goal_id: int,
    service: GoalService = Depends(get_goal_service),
):
    return await service.get_goal(goal_id)


@router.patch("/{goal_id}", response_model=GoalResponse)
async def update_goal(
    goal_id: int,
    body: GoalUpdate,
    service: GoalService = Depends(get_goal_service),
):
    """Update goal status, deadline, or priority."""
    return await service.update_goal(goal_id, body)


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_goal(
    goal_id: int,
    service: GoalService = Depends(get_goal_service),
):
    await service.delete_goal(goal_id)
