# backend/ai/agent.py
#
# Stage 2: Extended agent loop that supports planning (write tools).
#
# Key changes from Stage 1:
#   1. MAX_TOOL_CALLS increased to 8 (planning needs 4 reads + 1 write)
#   2. AgentResult now includes an optional plan_id
#   3. Write tool failures are captured and returned gracefully
#   4. user_id is always injected from DEV_USER_ID for all tools
#
# The agent loop itself is UNCHANGED from Stage 1.
# This demonstrates the key insight: the loop is generic.
# Adding new tools (even write tools) does not change the loop.
# Only TOOL_FUNCTIONS and TOOL_SCHEMA change.

import logging
from dataclasses import dataclass, field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
import google.generativeai as genai

from backend.ai.client import get_gemini_model
from backend.ai.tools import TOOL_FUNCTIONS, TOOL_SCHEMA
from backend.core.exceptions import AIServiceError

logger = logging.getLogger(__name__)

# Planning requires more tool calls: 4 reads + 1 write + possible retry
MAX_TOOL_CALLS = 8

# Hardcoded dev user ID — no auth yet (Stage 3)
DEV_USER_ID = 1


@dataclass
class ToolCallRecord:
    """Records what happened during a single tool call. Returned in the API response."""
    tool: str
    args: dict
    result_summary: str
    success: bool = True
    error: str = ""


@dataclass
class AgentResult:
    """The final result from a complete agent run."""
    response: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    plan_id: Optional[int] = None  # Set if create_study_plan was called successfully


async def run_agent(user_message: str, db: AsyncSession) -> AgentResult:
    """
    Run the agent loop for a single user message.

    The loop is identical to Stage 1. The difference is in TOOL_FUNCTIONS:
    it now includes get_goals, get_pending_revisions, and create_study_plan.

    The model decides which tools to call. The loop executes them.
    """
    model = get_gemini_model()
    tool_call_records: list[ToolCallRecord] = []
    created_plan_id: Optional[int] = None

    messages = [{"role": "user", "parts": [user_message]}]

    for iteration in range(MAX_TOOL_CALLS + 1):

        if iteration == MAX_TOOL_CALLS:
            raise AIServiceError(
                f"Agent exceeded maximum tool calls ({MAX_TOOL_CALLS}). "
                "This may indicate the model is stuck in a loop."
            )

        # ── Call Gemini ──────────────────────────────────────────────────────
        try:
            response = model.generate_content(
                contents=messages,
                tools=[TOOL_SCHEMA],
            )
        except Exception as e:
            raise AIServiceError(f"Gemini API error: {str(e)}")

        candidate = response.candidates[0]
        parts = candidate.content.parts

        # ── Detect function_call ─────────────────────────────────────────────
        function_call_part = None
        for part in parts:
            if hasattr(part, "function_call") and part.function_call.name:
                function_call_part = part
                break

        # ── Option A: Tool requested ─────────────────────────────────────────
        if function_call_part is not None:
            fc = function_call_part.function_call
            tool_name = fc.name
            tool_args = dict(fc.args)

            logger.info(f"[Agent] Tool call: {tool_name}({tool_args})")

            # Safety: reject unknown tool names
            if tool_name not in TOOL_FUNCTIONS:
                raise AIServiceError(
                    f"Model requested unknown tool: '{tool_name}'. "
                    f"Allowed tools: {list(TOOL_FUNCTIONS.keys())}"
                )

            tool_func = TOOL_FUNCTIONS[tool_name]

            # Always inject user_id from the trusted server-side value
            # The LLM may pass user_id but we override it — the client cannot
            # be trusted to provide the correct user_id (security boundary)
            tool_args["user_id"] = DEV_USER_ID

            try:
                tool_result = await tool_func(db=db, **tool_args)

                # If this was create_study_plan and it succeeded, capture the plan_id
                if tool_name == "create_study_plan" and isinstance(tool_result, dict):
                    if tool_result.get("success") and tool_result.get("plan_id"):
                        created_plan_id = tool_result["plan_id"]

                record = ToolCallRecord(
                    tool=tool_name,
                    args={k: v for k, v in tool_args.items() if k != "user_id"},
                    result_summary=(
                        f"plan_id={tool_result.get('plan_id')}, tasks={tool_result.get('tasks_created')}"
                        if tool_name == "create_study_plan"
                        else f"returned {len(str(tool_result))} chars"
                    ),
                    success=True,
                )
            except Exception as e:
                record = ToolCallRecord(
                    tool=tool_name,
                    args=tool_args,
                    result_summary="",
                    success=False,
                    error=str(e),
                )
                tool_call_records.append(record)
                raise AIServiceError(f"Tool '{tool_name}' failed: {str(e)}")

            tool_call_records.append(record)

            # Add model turn and tool result to message history
            messages.append(candidate.content)
            messages.append(
                genai.protos.Content(
                    role="user",
                    parts=[
                        genai.protos.Part(
                            function_response=genai.protos.FunctionResponse(
                                name=tool_name,
                                response={"result": tool_result}
                            )
                        )
                    ]
                )
            )
            continue

        # ── Option B: Final text response ────────────────────────────────────
        try:
            final_text = response.text
        except Exception:
            final_text = "I could not generate a response. Please try rephrasing."

        logger.info(f"[Agent] Finished after {iteration} tool call(s)")

        return AgentResult(
            response=final_text,
            tool_calls=tool_call_records,
            plan_id=created_plan_id,
        )

    raise AIServiceError("Unexpected agent loop exit")
