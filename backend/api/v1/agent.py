# backend/api/v1/agent.py
#
# WHAT: The FastAPI endpoint that triggers the agent loop.
# WHY IT IS THIN: The endpoint does only three things:
#   1. Parse the incoming JSON request
#   2. Call run_agent() (the actual logic lives in ai/agent.py)
#   3. Return the result as JSON
#
# FASTAPI CONCEPT: Depends(get_db) for database sessions
#   The db session is injected by FastAPI automatically.
#   The agent receives the session and passes it to tools.
#   The session is committed/rolled back by get_db() after the request.
#
# NOTE ON USER_ID:
#   Stage 1 uses a hardcoded DEV_USER_ID=1 (defined in agent.py).
#   This is intentional and documented. Authentication is Stage 3.
#   To test, create a user with id=1 in your database first.

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.session import get_db
from backend.ai.agent import run_agent, ToolCallRecord
from backend.core.exceptions import AIServiceError

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


class ToolCallSummary(BaseModel):
    tool: str
    args: dict
    result_summary: str
    success: bool
    error: str = ""


class ChatResponse(BaseModel):
    response: str
    tool_calls: list[ToolCallSummary]


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Send a message to the PrepPilot AI agent.

    The agent will:
    1. Decide whether it needs to call any tools (get_user_progress, get_weak_topics)
    2. Execute the tools against the real database
    3. Use the results to generate a contextual response

    **Stage 1 limitation**: Uses a hardcoded user_id=1. Add data for that user first.

    Example requests:
    - "How am I doing in DSA?"
    - "What topics am I weak at?"
    - "What is dynamic programming?" (no tool call needed)
    """
    result = await run_agent(user_message=body.message, db=db)

    return ChatResponse(
        response=result.response,
        tool_calls=[
            ToolCallSummary(
                tool=tc.tool,
                args=tc.args,
                result_summary=tc.result_summary,
                success=tc.success,
                error=tc.error,
            )
            for tc in result.tool_calls
        ],
    )
