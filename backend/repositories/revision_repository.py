# backend/repositories/revision_repository.py

from datetime import date
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.revision import Revision, RevisionStatus
from backend.schemas.revision import RevisionCreate, RevisionUpdate


class RevisionRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, revision_id: int) -> Optional[Revision]:
        result = await self.db.execute(
            select(Revision).where(Revision.id == revision_id)
        )
        return result.scalar_one_or_none()

    async def get_by_user(self, user_id: int, skip: int = 0, limit: int = 100) -> list[Revision]:
        result = await self.db.execute(
            select(Revision)
            .where(Revision.user_id == user_id)
            .order_by(Revision.planned_date.asc())
            .offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def get_pending(self, user_id: int) -> list[Revision]:
        """
        Return all pending revisions whose planned_date has passed.
        This is the core 'revision debt' query used by the AI agent.
        Overdue = PENDING and planned_date <= today.
        """
        today = date.today()
        result = await self.db.execute(
            select(Revision)
            .where(
                Revision.user_id == user_id,
                Revision.status == RevisionStatus.PENDING.value,
                Revision.planned_date <= today,
            )
            .order_by(Revision.planned_date.asc())  # oldest debt first
        )
        return list(result.scalars().all())

    async def create(self, data: RevisionCreate) -> Revision:
        revision = Revision(**data.model_dump())
        self.db.add(revision)
        await self.db.flush()
        await self.db.refresh(revision)
        return revision

    async def update(self, revision: Revision, data: RevisionUpdate) -> Revision:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(revision, field, value)
        await self.db.flush()
        await self.db.refresh(revision)
        return revision

    async def delete(self, revision: Revision) -> None:
        await self.db.delete(revision)
        await self.db.flush()
