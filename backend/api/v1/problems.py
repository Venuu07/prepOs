# backend/api/v1/problems.py
#
# FASTAPI CONCEPT: Nested routes for sub-resources
# POST /api/v1/problems/{problem_id}/attempts is a "nested" route.
# This is standard REST — an attempt belongs to a problem, so its URL
# lives under the problem's URL. FastAPI handles nested routes naturally.

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.session import get_db
from backend.services.problem_service import ProblemService
from backend.schemas.problem import (
    ProblemCreate, ProblemUpdate, ProblemResponse,
    ProblemAttemptCreate, ProblemAttemptResponse,
)

router = APIRouter()


def get_problem_service(db: AsyncSession = Depends(get_db)) -> ProblemService:
    return ProblemService(db)


@router.post("/", response_model=ProblemResponse, status_code=status.HTTP_201_CREATED)
async def create_problem(
    body: ProblemCreate,
    service: ProblemService = Depends(get_problem_service),
):
    """Add a new problem to track."""
    return await service.create_problem(body)


@router.get("/", response_model=list[ProblemResponse])
async def list_problems(
    user_id: int,
    topic_id: int | None = None,
    skip: int = 0,
    limit: int = 100,
    service: ProblemService = Depends(get_problem_service),
):
    """List problems for a user. Filter by topic with ?topic_id=<id>."""
    return await service.list_problems(user_id=user_id, topic_id=topic_id, skip=skip, limit=limit)


@router.get("/{problem_id}", response_model=ProblemResponse)
async def get_problem(
    problem_id: int,
    service: ProblemService = Depends(get_problem_service),
):
    return await service.get_problem(problem_id)


@router.patch("/{problem_id}", response_model=ProblemResponse)
async def update_problem(
    problem_id: int,
    body: ProblemUpdate,
    service: ProblemService = Depends(get_problem_service),
):
    """Update status, confidence, notes, etc."""
    return await service.update_problem(problem_id, body)


@router.delete("/{problem_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_problem(
    problem_id: int,
    service: ProblemService = Depends(get_problem_service),
):
    """Soft-delete a problem (preserves attempt history)."""
    await service.delete_problem(problem_id)


# ── Problem Attempts (nested routes) ─────────────────────────────────────────

@router.post("/{problem_id}/attempts",
             response_model=ProblemAttemptResponse,
             status_code=status.HTTP_201_CREATED)
async def log_attempt(
    problem_id: int,
    body: ProblemAttemptCreate,
    service: ProblemService = Depends(get_problem_service),
):
    """
    Log a new attempt at a problem.
    Also automatically updates the problem's status and last_solved_date.
    """
    # Ensure the URL problem_id matches the body — belt and suspenders
    body.problem_id = problem_id
    return await service.log_attempt(body)


@router.get("/{problem_id}/attempts", response_model=list[ProblemAttemptResponse])
async def get_attempts(
    problem_id: int,
    service: ProblemService = Depends(get_problem_service),
):
    """Get all attempts for a problem, newest first."""
    return await service.get_attempts(problem_id)
