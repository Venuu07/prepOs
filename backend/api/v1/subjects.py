# backend/api/v1/subjects.py
#
# WHY THE ROUTER IS THIN:
#
# This file only does three things per endpoint:
#   1. Declare the HTTP method, path, and response shape
#   2. Call the service
#   3. Return the result
#
# No SQL here. No business logic here.
# If a rule changes (e.g. "subjects must have a short_code"), you change the
# SERVICE — the router stays untouched.

# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, status
# pyrefly: ignore [missing-import]
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.session import get_db
from backend.services.subject_service import SubjectService
from backend.schemas.subject import SubjectCreate, SubjectUpdate, SubjectResponse

router = APIRouter()

# ── Dependency helper ─────────────────────────────────────────────────────────
# Instead of writing SubjectService(db) in every route, we define it once here.
# FastAPI will call get_subject_service() automatically and inject its return value.

def get_subject_service(db: AsyncSession = Depends(get_db)) -> SubjectService:
    return SubjectService(db)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/",
    response_model=SubjectResponse,
    status_code=status.HTTP_201_CREATED,  # 201 Created, not 200 OK — semantically correct for creation
    summary="Create a new subject",
)

async def create_subject(
    body: SubjectCreate,
    service: SubjectService = Depends(get_subject_service),
):
    """
    Create a new top-level subject (e.g. Operating Systems, DBMS, DSA).

    - **name**: required, must be unique
    - **short_code**: optional, e.g. "OS", "DBMS"
    - **description**: optional
    """
    return await service.create_subject(body)


@router.get(
    "/",
    response_model=list[SubjectResponse],
    summary="List all subjects",
)

async def list_subjects(
    skip: int = 0,
    limit: int = 100,
    service: SubjectService = Depends(get_subject_service),
):
    """
    Return all subjects.

    Use `skip` and `limit` for pagination:
    - `skip=0&limit=10` → first page
    - `skip=10&limit=10` → second page
    """
    return await service.list_subjects(skip=skip, limit=limit)


@router.get(
    "/{subject_id}",
    response_model=SubjectResponse,
    summary="Get a subject by ID",
)
async def get_subject(
    subject_id: int,
    service: SubjectService = Depends(get_subject_service),
):
    """Return a single subject. Returns 404 if not found."""
    return await service.get_subject(subject_id)


@router.patch(
    "/{subject_id}",
    response_model=SubjectResponse,
    summary="Partially update a subject",
)
async def update_subject(
    subject_id: int,
    body: SubjectUpdate,
    service: SubjectService = Depends(get_subject_service),
):
    """
    Update one or more fields of a subject.

    Only include the fields you want to change.
    Omitted fields are left as-is.
    """
    return await service.update_subject(subject_id, body)


@router.delete(
    "/{subject_id}",
    status_code=status.HTTP_204_NO_CONTENT,  # 204 = success, no body returned
    summary="Delete a subject",
)
async def delete_subject(
    subject_id: int,
    service: SubjectService = Depends(get_subject_service),
):
    """
    Delete a subject and all its topics (cascade).
    Returns 204 No Content on success. Returns 404 if not found.
    """
    await service.delete_subject(subject_id)
    # No return value — 204 responses must have no body.
