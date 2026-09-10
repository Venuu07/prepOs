# backend/repositories/topic_repository.py
#
# DATA FLOW: API Router → TopicService → TopicRepository → AsyncSession → Neon DB
# The repository is the ONLY layer that writes SQL.

from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.topic import Topic
from backend.schemas.topic import TopicCreate, TopicUpdate


class TopicRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, topic_id: int) -> Optional[Topic]:
        result = await self.db.execute(select(Topic).where(Topic.id == topic_id))
        return result.scalar_one_or_none()

    async def get_by_subject(self, subject_id: int) -> list[Topic]:
        result = await self.db.execute(
            select(Topic)
            .where(Topic.subject_id == subject_id)
            .order_by(Topic.order_index)
        )
        return list(result.scalars().all())

    async def get_all(self, skip: int = 0, limit: int = 100) -> list[Topic]:
        result = await self.db.execute(
            select(Topic).order_by(Topic.subject_id, Topic.order_index)
            .offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def create(self, data: TopicCreate) -> Topic:
        topic = Topic(**data.model_dump())
        self.db.add(topic)
        await self.db.flush()
        await self.db.refresh(topic)
        return topic

    async def update(self, topic: Topic, data: TopicUpdate) -> Topic:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(topic, field, value)
        await self.db.flush()
        await self.db.refresh(topic)
        return topic

    async def delete(self, topic: Topic) -> None:
        await self.db.delete(topic)
        await self.db.flush()
