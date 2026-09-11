# backend/api/v1/revisions.py

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.session import get_db
from backend.services.revision_service import RevisionService
from backend.schemas.revision import RevisionCreate, RevisionUpdate, RevisionResponse

router = APIRouter()


def get_revision_service(db: AsyncSession = Depends(get_db)) -> RevisionService:
    return RevisionService(db)


@router.post("/", response_model=RevisionResponse, status_code=status.HTTP_201_CREATED)
async def create_revision(
    body: RevisionCreate,
    service: RevisionService = Depends(get_revision_service),
):
    """Schedule a revision for a topic."""
    return await service.create_revision(body)


@router.get("/", response_model=list[RevisionResponse])
async def list_revisions(
    user_id: int,
    skip: int = 0,
    limit: int = 100,
    service: RevisionService = Depends(get_revision_service),
):
    """List all revisions for a user ordered by planned_date."""
    return await service.list_revisions(user_id, skip=skip, limit=limit)


@router.get("/overdue", response_model=list[RevisionResponse])
async def get_overdue_revisions(
    user_id: int,
    service: RevisionService = Depends(get_revision_service),
):
    """
    Return all PENDING revisions whose planned_date has passed.
    This is the 'revision debt' endpoint — used by the AI agent.
    """
    return await service.get_overdue(user_id)


@router.get("/{revision_id}", response_model=RevisionResponse)
async def get_revision(
    revision_id: int,
    service: RevisionService = Depends(get_revision_service),
):
    return await service.get_revision(revision_id)


@router.patch("/{revision_id}", response_model=RevisionResponse)
async def update_revision(
    revision_id: int,
    body: RevisionUpdate,
    service: RevisionService = Depends(get_revision_service),
):
    """Mark a revision as COMPLETED or SKIPPED, or reschedule it."""
    return await service.update_revision(revision_id, body)


@router.delete("/{revision_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_revision(
    revision_id: int,
    service: RevisionService = Depends(get_revision_service),
):
    await service.delete_revision(revision_id)
