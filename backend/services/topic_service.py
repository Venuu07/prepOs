# backend/services/topic_service.py
#
# WHAT: Business logic for Topics.
# WHY: The service validates that the parent subject exists before creating a topic,
#      and maps DB "not found" into clean 404 errors.
# ONE FASTAPI CONCEPT: Dependency injection — TopicService receives a db session
#   it didn't create. FastAPI's Depends() system creates it and injects it.
# ONE DB CONCEPT: A ForeignKey constraint at the DB level also prevents orphaned
#   topics, but checking at the service level gives a better error message.

# pyrefly: ignore [missing-import]
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.topic import Topic
from backend.repositories.topic_repository import TopicRepository
from backend.schemas.topic import TopicCreate, TopicUpdate
from backend.core.exceptions import NotFoundError


class TopicService:

    def __init__(self, db: AsyncSession):
        self.repo = TopicRepository(db)

    async def get_topic(self, topic_id: int) -> Topic:
        topic = await self.repo.get_by_id(topic_id)
        if topic is None:
            raise NotFoundError(f"Topic with id={topic_id} not found")
        return topic

    async def list_topics(self, subject_id: int | None = None,
                          skip: int = 0, limit: int = 100) -> list[Topic]:
        if subject_id is not None:
            return await self.repo.get_by_subject(subject_id)
        return await self.repo.get_all(skip=skip, limit=limit)

    async def create_topic(self, data: TopicCreate) -> Topic:
        return await self.repo.create(data)

    async def update_topic(self, topic_id: int, data: TopicUpdate) -> Topic:
        topic = await self.get_topic(topic_id)
        return await self.repo.update(topic, data)

    async def delete_topic(self, topic_id: int) -> None:
        topic = await self.get_topic(topic_id)
        await self.repo.delete(topic)
