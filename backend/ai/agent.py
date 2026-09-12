# backend/ai/agent.py
#
# WHAT: The agent loop. This is the core of Stage 1.
# WHY: The agent is what makes this "agentic" rather than a simple LLM call.
#   It loops, detects tool calls, executes them, and feeds results back.
#
# THE LOOP (simplified):
#   messages = [user_message]
#   while not done:
#       response = gemini(messages, tools)
#       if response wants a tool:
#           result = execute_tool(tool_name, tool_args)
#           messages.append(model_turn)
#           messages.append(tool_result)
#       else:
#           return response.text   <-- done
#
# CONCEPT: Why do we manually manage messages instead of using ChatSession?
#   ChatSession is a convenience wrapper that hides the message list.
#   For learning, we manage messages ourselves so you can see every turn.
#   In production, you might use ChatSession, but understanding the raw
#   message structure is essential before using abstractions.
#
# CONCEPT: google.generativeai function calling format
#   When Gemini wants a tool, response.candidates[0].content.parts[0]
#   has a .function_call attribute with .name and .args.
#   When we return a result, we create a Part with .function_response.
#   Both the model turn and the tool result are added to messages.

import json
import logging
from dataclasses import dataclass, field
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
import google.generativeai as genai

from backend.ai.client import get_gemini_model
from backend.ai.tools import TOOL_FUNCTIONS, TOOL_SCHEMA
from backend.core.exceptions import AIServiceError

logger = logging.getLogger(__name__)

# Safety limit: stop after this many tool calls to prevent infinite loops
MAX_TOOL_CALLS = 5

# Hardcoded dev user ID for Stage 1 (no auth yet)
# IMPORTANT: In Stage 2, this will come from an auth token
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


async def run_agent(user_message: str, db: AsyncSession) -> AgentResult:
    """
    Run the agent loop for a single user message.

    This is the main entry point called by the FastAPI endpoint.
    
    Args:
        user_message: The user natural-language question
        db: SQLAlchemy async session for database access
    
    Returns:
        AgentResult with the final response and a log of tool calls made
    """
    model = get_gemini_model()
    tool_call_records: list[ToolCallRecord] = []

    # ── Build initial messages list ──────────────────────────────────────────
    # CONCEPT: Messages are the conversation history sent to the model.
    # We start with just the user message.
    # As the agent loop runs, we append model turns and tool results.
    # The full history is resent on every API call (LLMs are stateless).
    messages = [
        {"role": "user", "parts": [user_message]}
    ]

    # ── Agent loop ───────────────────────────────────────────────────────────
    for iteration in range(MAX_TOOL_CALLS + 1):

        if iteration == MAX_TOOL_CALLS:
            raise AIServiceError(
                f"Agent exceeded maximum tool calls ({MAX_TOOL_CALLS}). "
                "This may indicate the model is stuck in a loop."
            )

        # ── Call Gemini ──────────────────────────────────────────────────────
        # Send the full message history + available tool schemas.
        # The model reads the messages and tool descriptions, then decides:
        #   Option A: Call a tool and return a function_call
        #   Option B: Give a final text answer
        try:
            response = model.generate_content(
                contents=messages,
                tools=[TOOL_SCHEMA],
            )
        except Exception as e:
            raise AIServiceError(f"Gemini API error: {str(e)}")

        # ── Inspect the response ─────────────────────────────────────────────
        # CONCEPT: Checking for function_call vs text
        # The response has candidates[0].content.parts — a list of parts.
        # Each part is either a text part or a function_call part.
        # We check for function_call first.
        candidate = response.candidates[0]
        parts = candidate.content.parts

        # Find any function_call in the parts
        function_call_part = None
        for part in parts:
            if hasattr(part, "function_call") and part.function_call.name:
                function_call_part = part
                break

        # ── Option A: Model requested a tool ────────────────────────────────
        if function_call_part is not None:
            fc = function_call_part.function_call
            tool_name = fc.name
            # fc.args is a MapComposite (proto map) — convert to plain dict
            tool_args = dict(fc.args)

            logger.info(f"[Agent] Tool call requested: {tool_name}({tool_args})")

            # ── Execute the tool ─────────────────────────────────────────────
            # CONCEPT: Dispatch table
            # We look up the function by name in TOOL_FUNCTIONS dict.
            # If the model hallucinates a tool name, we catch it here.
            if tool_name not in TOOL_FUNCTIONS:
                raise AIServiceError(
                    f"Model requested unknown tool: '{tool_name}'. "
                    f"Available tools: {list(TOOL_FUNCTIONS.keys())}"
                )

            tool_func = TOOL_FUNCTIONS[tool_name]

            # Inject user_id if the tool expects it and it was not provided
            # This is how we handle the "no auth yet" situation:
            # the model might ask for user_id but we use the dev default.
            if "user_id" not in tool_args:
                tool_args["user_id"] = DEV_USER_ID

            try:
                tool_result = await tool_func(db=db, **tool_args)
                record = ToolCallRecord(
                    tool=tool_name,
                    args=tool_args,
                    result_summary=f"Returned {len(str(tool_result))} chars of data",
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

            # ── Add the model turn and tool result to message history ────────
            # CONCEPT: Adding turns to messages
            # After a tool call, we add TWO things to the messages list:
            #
            # 1. The model turn (what Gemini returned — the function_call)
            #    This tells future model calls: "I previously requested this tool"
            #
            # 2. The function_response (our tool result)
            #    This tells the model: "here is what the tool returned"
            #
            # Note: function_response parts are sent with role="user"
            # This is the Gemini SDK convention. It looks odd but is correct.

            # Add the model turn (preserves the function_call)
            messages.append(candidate.content)

            # Add the tool result
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

            # Loop again — give the result back to the model
            continue

        # ── Option B: Model gave a final text answer ─────────────────────────
        # No function_call found — the model produced a plain text response.
        # Extract the text and return it.
        try:
            final_text = response.text
        except Exception:
            # response.text raises if the response was blocked or empty
            final_text = "I could not generate a response. Please try rephrasing."

        logger.info(f"[Agent] Final response after {iteration} tool call(s)")

        return AgentResult(
            response=final_text,
            tool_calls=tool_call_records,
        )

    # This line should be unreachable (the loop always returns or raises)
    raise AIServiceError("Unexpected agent loop exit")
