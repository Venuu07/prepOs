from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    The base class that all PrepOS SQLAlchemy models inherit from.

    Inheriting from this class gives a Python class:
    - A __tablename__ (if you define it)
    - Column mapping (via Mapped[] type annotations)
    - Relationship support (via relationship())
    - Automatic registration in Base.metadata

    Usage:
        class User(Base):
            __tablename__ = "users"
            id: Mapped[int] = mapped_column(primary_key=True)
    """
    pass
