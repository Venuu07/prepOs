# backend/services/revision_service.py

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.revision import Revision
from backend.repositories.revision_repository import RevisionRepository
from backend.schemas.revision import RevisionCreate, RevisionUpdate
from backend.core.exceptions import NotFoundError


class RevisionService:

    def __init__(self, db: AsyncSession):
        self.repo = RevisionRepository(db)

    async def get_revision(self, revision_id: int) -> Revision:
        revision = await self.repo.get_by_id(revision_id)
        if revision is None:
            raise NotFoundError(f"Revision with id={revision_id} not found")
        return revision

    async def list_revisions(self, user_id: int, skip: int = 0, limit: int = 100) -> list[Revision]:
        return await self.repo.get_by_user(user_id, skip=skip, limit=limit)

    async def get_overdue(self, user_id: int) -> list[Revision]:
        """Return all revisions whose planned_date has passed and are still PENDING."""
        return await self.repo.get_pending(user_id)

    async def create_revision(self, data: RevisionCreate) -> Revision:
        return await self.repo.create(data)

    async def update_revision(self, revision_id: int, data: RevisionUpdate) -> Revision:
        revision = await self.get_revision(revision_id)
        return await self.repo.update(revision, data)

    async def delete_revision(self, revision_id: int) -> None:
        revision = await self.get_revision(revision_id)
        await self.repo.delete(revision)
