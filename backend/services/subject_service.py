# backend/services/subject_service.py
#
# WHY A SERVICE LAYER:
#
# The service sits between the API router and the repository.
# Its job is business logic — decisions that aren't just "fetch from DB"
# but aren't HTTP concerns either.
#
# In this case:
#   - Check for duplicate names before creating (business rule)
#   - Convert database exceptions (IntegrityError) into domain exceptions (ConflictError)
#   - Ensure "not found" is handled consistently, not scattered across routes
#
# The router should be thin: validate input, call service, return response.
# The repository should be dumb: just run the SQL.
# The service is where the logic lives.

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.subject import Subject
from backend.repositories.subject_repository import SubjectRepository
from backend.schemas.subject import SubjectCreate, SubjectUpdate
from backend.core.exceptions import NotFoundError, ConflictError


class SubjectService:

    def __init__(self, db: AsyncSession):
        self.repo = SubjectRepository(db)

    async def get_subject(self, subject_id: int) -> Subject:
        """
        Fetch a subject by id.
        Raises NotFoundError (→ 404) if it doesn't exist.
        """
        subject = await self.repo.get_by_id(subject_id)
        if subject is None:
            raise NotFoundError(f"Subject with id={subject_id} not found")
        return subject

    async def list_subjects(self, skip: int = 0, limit: int = 100) -> list[Subject]:
        """Return all subjects with optional pagination."""
        return await self.repo.get_all(skip=skip, limit=limit)

    async def create_subject(self, data: SubjectCreate) -> Subject:
        """
        Create a new subject.

        Business rules enforced here:
          1. Name must be unique (case-insensitive check before insert)
          2. short_code must be unique (caught by DB constraint → IntegrityError)
        """
        # Check name uniqueness before hitting the DB constraint.
        # This gives a clearer error than the raw IntegrityError message.
        existing = await self.repo.get_by_name(data.name)
        if existing:
            raise ConflictError(
                f"A subject named '{data.name}' already exists (id={existing.id})"
            )

        try:
            return await self.repo.create(data)
        except IntegrityError as e:
            # This catches the short_code unique constraint violation
            # (and any other DB-level constraint we might have missed above).
            raise ConflictError(
                "Subject could not be created due to a duplicate value. "
                "Check that the name and short_code are unique."
            ) from e

    async def update_subject(self, subject_id: int, data: SubjectUpdate) -> Subject:
        """
        Partially update a subject.
        Raises NotFoundError if the subject doesn't exist.
        Raises ConflictError if the new name or short_code conflicts.
        """
        subject = await self.get_subject(subject_id)  # raises 404 if missing

        # If the client is changing the name, check it won't conflict.
        if data.name is not None and data.name.lower() != subject.name.lower():
            existing = await self.repo.get_by_name(data.name)
            if existing:
                raise ConflictError(
                    f"A subject named '{data.name}' already exists (id={existing.id})"
                )

        try:
            return await self.repo.update(subject, data)
        except IntegrityError as e:
            raise ConflictError(
                "Update failed due to a duplicate short_code or name."
            ) from e

    async def delete_subject(self, subject_id: int) -> None:
        """
        Delete a subject by id.
        Raises NotFoundError if it doesn't exist.
        """
        subject = await self.get_subject(subject_id)  # raises 404 if missing
        await self.repo.delete(subject)
