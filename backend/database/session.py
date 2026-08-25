# backend/database/session.py
#


# pyrefly: ignore [missing-import]
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from backend.core.config import get_settings

settings = get_settings()

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=settings.debug,           # Log SQL in debug mode
    pool_size=10,                  # Persistent connections in pool
    max_overflow=20,               # Extra connections allowed at peak
    pool_timeout=30,               # Seconds to wait for a free connection
    pool_recycle=1800,             # Recycle connections after 30 minutes
    pool_pre_ping=True,            # Check connection is alive before using
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=True,   # Auto-flush pending changes before queries (default)
    autocommit=False, # We manage transactions explicitly (default)
)


# ── FastAPI Dependency ────────────────────────────────────────────────────────
async def get_db() -> AsyncSession:
    """
    FastAPI dependency that provides a database session for a single request.

    This is an async generator. FastAPI's Depends() system understands generators:
    - Code before yield: setup (open session)
    - yield: provide the value to the route handler
    - Code after yield (in finally): teardown (close session, return connection to pool)

    Usage in a route handler:
        from fastapi import Depends
        from sqlalchemy.ext.asyncio import AsyncSession
        from backend.database.session import get_db

        @router.get("/things")
        async def get_things(db: AsyncSession = Depends(get_db)):
            # db is a fresh session for this request
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            
            await session.commit()
        except Exception:
            
            await session.rollback()
            raise
        finally:
           
            await session.close()
