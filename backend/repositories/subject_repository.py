# backend/repositories/subject_repository.py
#
# WHY A REPOSITORY LAYER:
#
# The repository is the ONLY place in the codebase that writes SQL.
# Every other layer (service, API) calls repository methods — they never
# touch the database directly.
#
# Benefits:
#   - One place to change if you swap databases or ORM versions
#   - Easy to mock in tests (replace repository with a fake that returns dummy data)
#   - Forces you to name your DB operations clearly: get_by_id, get_by_name, etc.

from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from backend.models.subject import Subject
from backend.schemas.subject import SubjectCreate, SubjectUpdate


class SubjectRepository:
    """
    Handles all database operations for the Subject model.
    Instantiated per-request, receives the session via dependency injection.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, subject_id: int) -> Optional[Subject]:
        """Return a single Subject by primary key, or None if not found."""
        result = await self.db.execute(
            select(Subject).where(Subject.id == subject_id)
        )
        return result.scalar_one_or_none()
        # scalar_one_or_none():
        #   - returns the object if exactly one row matched
        #   - returns None if zero rows matched
        #   - raises an exception if more than one row matched (impossible here since id is PK)

    async def get_by_name(self, name: str) -> Optional[Subject]:
        """Return a Subject matching the given name (case-insensitive), or None."""
        result = await self.db.execute(
            select(Subject).where(func.lower(Subject.name) == name.lower())
        )
        return result.scalar_one_or_none()

    async def get_all(self, skip: int = 0, limit: int = 100) -> list[Subject]:
        """
        Return all subjects, ordered by name.
        skip + limit implement pagination:
          skip=0, limit=10  → first 10 results
          skip=10, limit=10 → next 10 results
        """
        result = await self.db.execute(
            select(Subject)
            .order_by(Subject.name)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())
        # scalars() unwraps the Row objects → gives us Subject instances directly
        # .all() executes and returns a list

    async def create(self, data: SubjectCreate) -> Subject:
        """
        Insert a new Subject row. Returns the created object with its generated id.

        Raises IntegrityError if name or short_code already exists (unique constraint).
        The SERVICE layer catches this and converts it to a ConflictError.
        """
        subject = Subject(
            name=data.name,
            short_code=data.short_code,
            description=data.description,
        )
        self.db.add(subject)
        # db.add() stages the object — it's not written to DB yet.
        # The session.commit() in get_db() (session.py) persists it after the request.
        # We flush here to get the auto-generated id back immediately.
        await self.db.flush()
        # flush() sends the INSERT to the DB within the current transaction
        # but does NOT commit. This gives us the id without ending the transaction.
        await self.db.refresh(subject)
        # refresh() re-reads the row from DB to populate server-side defaults
        # (e.g. created_at which is set by server_default=func.now())
        return subject

    async def update(self, subject: Subject, data: SubjectUpdate) -> Subject:
        """
        Apply partial updates to an existing Subject.
        Only updates fields that were explicitly provided (not None).
        """
        update_data = data.model_dump(exclude_unset=True)
        # model_dump(exclude_unset=True) returns only the fields the client
        # actually sent — fields they omitted are NOT in this dict.
        # This is what makes PATCH work correctly.

        for field, value in update_data.items():
            setattr(subject, field, value)
            # setattr(obj, "name", "DBMS") is equivalent to obj.name = "DBMS"
            # We use it here to dynamically set fields from a dict.

        await self.db.flush()
        await self.db.refresh(subject)
        return subject

    async def delete(self, subject: Subject) -> None:
        """Delete a Subject row. Cascades to Topics per the model definition."""
        await self.db.delete(subject)
        await self.db.flush()
