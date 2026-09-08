# backend/schemas/subject.py
#
# WHY SCHEMAS EXIST SEPARATELY FROM MODELS:
#
# The SQLAlchemy model (models/subject.py) describes the DATABASE TABLE.
# Pydantic schemas describe what the API ACCEPTS and RETURNS.
#
# They look similar but serve different purposes:
#   - SQLAlchemy model  → talks to the database (rows, columns, relationships)
#   - Pydantic schema   → validates HTTP request bodies, shapes HTTP responses
#
# Keeping them separate means you can:
#   - Return only safe fields (never accidentally expose internal DB columns)
#   - Accept different fields for create vs update
#   - Add API-level validation without touching the DB model

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class SubjectCreate(BaseModel):
    """
    Shape of the request body for POST /api/v1/subjects.
    The client must send at minimum a `name`.
    """
    name: str = Field(
        ...,                        # ... means required (no default)
        min_length=2,
        max_length=200,
        examples=["Operating Systems"],
    )
    short_code: Optional[str] = Field(
        default=None,
        max_length=20,
        examples=["OS"],
    )
    description: Optional[str] = Field(
        default=None,
        examples=["Covers processes, memory management, scheduling, and file systems."],
    )

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name cannot be blank or whitespace")
        return v.strip()

    @field_validator("short_code")
    @classmethod
    def short_code_uppercase(cls, v: Optional[str]) -> Optional[str]:
        # Normalise short codes to uppercase: "os" → "OS"
        return v.strip().upper() if v else None


class SubjectUpdate(BaseModel):
    """
    Shape of the request body for PATCH /api/v1/subjects/{id}.
    All fields are Optional — the client only sends what they want to change.
    This is the PATCH pattern (partial update), not PUT (full replacement).
    """
    name: Optional[str] = Field(default=None, min_length=2, max_length=200)
    short_code: Optional[str] = Field(default=None, max_length=20)
    description: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("name cannot be blank or whitespace")
        return v.strip() if v else v

    @field_validator("short_code")
    @classmethod
    def short_code_uppercase(cls, v: Optional[str]) -> Optional[str]:
        return v.strip().upper() if v else None


class SubjectResponse(BaseModel):
    """
    Shape of what the API returns for a subject.
    Maps directly from the SQLAlchemy Subject model fields.
    `model_config = {"from_attributes": True}` enables reading from ORM objects.
    """
    id: int
    name: str
    short_code: Optional[str]
    description: Optional[str]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
    # WHY from_attributes=True:
    # Pydantic normally builds from dicts. SQLAlchemy returns objects.
    # This setting tells Pydantic: "read values from object attributes, not dict keys."
    # Without it: SubjectResponse(subject_orm_object) would fail.
