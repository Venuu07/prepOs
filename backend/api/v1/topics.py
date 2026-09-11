# backend/api/v1/topics.py
#
# FASTAPI CONCEPT: Optional query parameters
# `subject_id: int | None = None` in the function signature becomes
# a URL query param: GET /api/v1/topics?subject_id=3
# FastAPI reads it from the URL automatically — no parsing needed.

# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, status
# pyrefly: ignore [missing-import]
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.session import get_db
from backend.services.topic_service import TopicService
from backend.schemas.topic import TopicCreate, TopicUpdate, TopicResponse

router = APIRouter()


def get_topic_service(db: AsyncSession = Depends(get_db)) -> TopicService:
    return TopicService(db)


@router.post("/", response_model=TopicResponse, status_code=status.HTTP_201_CREATED)
async def create_topic(
    body: TopicCreate,
    service: TopicService = Depends(get_topic_service),
):
    """Create a new topic under a subject."""
    return await service.create_topic(body)


@router.get("/", response_model=list[TopicResponse])
async def list_topics(
    subject_id: int | None = None,
    skip: int = 0,
    limit: int = 100,
    service: TopicService = Depends(get_topic_service),
):
    """List all topics. Filter by subject_id using ?subject_id=<id>."""
    return await service.list_topics(subject_id=subject_id, skip=skip, limit=limit)


@router.get("/{topic_id}", response_model=TopicResponse)
async def get_topic(
    topic_id: int,
    service: TopicService = Depends(get_topic_service),
):
    return await service.get_topic(topic_id)


@router.patch("/{topic_id}", response_model=TopicResponse)
async def update_topic(
    topic_id: int,
    body: TopicUpdate,
    service: TopicService = Depends(get_topic_service),
):
    return await service.update_topic(topic_id, body)


@router.delete("/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_topic(
    topic_id: int,
    service: TopicService = Depends(get_topic_service),
):
    await service.delete_topic(topic_id)
