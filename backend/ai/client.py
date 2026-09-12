# backend/ai/client.py
#
# WHAT: A thin wrapper around the Google Gemini SDK.
# WHY: Keeps all SDK-specific setup in one place.
#   If we ever switch models or SDKs, we only change this file.
#   The rest of the codebase (tools.py, agent.py) never touches the SDK directly.
#
# IMPORTANT CONCEPT: google-generativeai 0.8.x API
#   genai.configure(api_key=...) sets the global API key.
#   genai.GenerativeModel(model_name, system_instruction=...) creates a model instance.
#   model.generate_content(contents, tools=...) sends the request.
#
# We do NOT use ChatSession here because it maintains internal state.
# The agent loop manages its own message history explicitly so we can
# inspect and control every turn. This is important for learning.

import google.generativeai as genai
from backend.core.config import get_settings
from backend.core.exceptions import AIServiceError


SYSTEM_INSTRUCTION = """You are PrepPilot, an intelligent preparation assistant for students.

You help students preparing for:
- Software placements and internships
- DSA (Data Structures & Algorithms)
- Core CS subjects (OS, DBMS, Networks, COA)
- GATE exam
- Competitive programming

You have access to tools that fetch the student real preparation data.
Always use tools to fetch data before answering specific questions about progress.
Never guess or fabricate numbers - use the tools.

When a user asks a general question that does not require data (e.g. "what is BFS?"),
answer directly without calling any tools.

Be concise, specific, and encouraging."""


def get_gemini_model() -> genai.GenerativeModel:
    """
    Initialize and return a configured Gemini GenerativeModel.

    Called once per agent request (not at import time) so that:
    - Settings are always fresh
    - API key errors surface clearly at request time, not at startup
    """
    settings = get_settings()

    if not settings.gemini_api_key:
        raise AIServiceError(
            "GEMINI_API_KEY is not configured. "
            "Add it to your .env file: GEMINI_API_KEY=your_key_here"
        )

    # Configure the global API key for this SDK version
    genai.configure(api_key=settings.gemini_api_key)

    model = genai.GenerativeModel(
        model_name=settings.gemini_model,
        system_instruction=SYSTEM_INSTRUCTION,
    )

    return model
