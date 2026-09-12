# backend/api/v1/agent.py
# Stage 2: Response now includes optional plan_id when a plan was created.

from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.session import get_db
from backend.ai.agent import run_agent

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
    plan_id: Optional[int] = None  # Set when create_study_plan succeeded


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Send a message to the PrepPilot AI planning agent.

    The agent supports two modes:
    - Q&A mode: "How am I doing?" / "What topics am I weak at?"
    - Planning mode: "Create a 7-day study plan for my interview"

    In planning mode the agent will:
    1. Fetch progress, weak topics, goals, and pending revisions
    2. Generate a structured study plan
    3. Validate it (hours, task durations, day numbers)
    4. Persist it to the database
    5. Return a human-readable confirmation with plan_id

    Stage 2 limitation: uses hardcoded user_id=1. Auth comes in Stage 3.

    Example planning request:
    {"message": "I have an interview in 7 days, 3 hours per day. Create a plan."}
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
        plan_id=result.plan_id,
    )
