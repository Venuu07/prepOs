# backend/main.py
#uvicorn backend.main:app --reload


from contextlib import asynccontextmanager
# pyrefly: ignore [missing-import]
from fastapi import FastAPI, Request
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware
# pyrefly: ignore [missing-import]
from fastapi.responses import JSONResponse

from backend.core.config import get_settings
from backend.core.exceptions import PrepOSError
from backend.database.session import engine
from backend.api.v1 import subjects as subjects_router
from backend.api.v1 import topics as topics_router
from backend.api.v1 import problems as problems_router
from backend.api.v1 import goals as goals_router
from backend.api.v1 import revisions as revisions_router
from backend.api.v1 import agent as agent_router



@asynccontextmanager
async def lifespan(app: FastAPI):
    # â”€â”€ STARTUP â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    settings = get_settings()
    print(f"[START] {settings.app_name} v{settings.app_version} starting up...")
    print(f"   Debug mode: {settings.debug}")

    # The async engine creates the connection pool lazily on first use,
    # but we can verify the connection is reachable during startup.
    # This catches misconfigured DATABASE_URL before the first request.
    try:
        async with engine.connect() as conn:
            # Use text() for a raw SQL ping query
            # pyrefly: ignore [missing-import]
            from sqlalchemy import text
            await conn.execute(text("SELECT 1"))
        print("   Database: [OK] connection pool initialized")
    except Exception as e:
        print(f"   Database: [FAIL] connection failed: {e}")
        print("   Is PostgreSQL running? Try: docker-compose up -d")
        # Don't raise here â€” let the server start even if DB is unreachable.
        # Individual requests will fail with a proper error.

    yield  # â† Server is running. Handling requests.

    # â”€â”€ SHUTDOWN â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    print("[STOP] PrepOS shutting down...")
    # Close the connection pool â€” waits for active connections to finish.
    await engine.dispose()
    print("   Database: connection pool closed.")



# â”€â”€ FastAPI App â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="""
PrepOS â€” AI-Native Preparation Intelligence Platform

An agentic AI system for intelligent preparation planning across
DSA, Core CS, GATE, and company-specific interview preparation.
    """,
    version=settings.app_version,
    docs_url="/docs",      # Swagger UI
    redoc_url="/redoc",    # ReDoc UI
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.exception_handler(PrepOSError)
async def prepos_exception_handler(request: Request, exc: PrepOSError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.__class__.__name__,
            "detail": exc.message,
        },
    )


# â”€â”€ Routers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
app.include_router(subjects_router.router,  prefix="/api/v1/subjects",  tags=["Subjects"])
app.include_router(topics_router.router,    prefix="/api/v1/topics",    tags=["Topics"])
app.include_router(problems_router.router,  prefix="/api/v1/problems",  tags=["Problems"])
app.include_router(goals_router.router,     prefix="/api/v1/goals",     tags=["Goals"])
app.include_router(revisions_router.router, prefix="/api/v1/revisions", tags=["Revisions"])
app.include_router(agent_router.router,     prefix="/api/v1/agent",     tags=["Agent"])


@app.get("/health", tags=["System"])
async def health_check():
    """
    Health check endpoint.
    Returns app status and version. Used by monitoring systems.
    """
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
    }


@app.get("/", tags=["System"])
async def root():
    """Root endpoint â€” confirms the API is reachable."""
    return {
        "message": "Welcome to PrepOS API",
        "docs": "/docs",
        "health": "/health",
    }


