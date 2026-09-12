# backend/ai/tools.py
#
# WHAT: The actual Python functions that the agent can call.
# WHY THEY EXIST HERE: These functions are the bridge between the LLM world
#   and the database world. The LLM requests them by name; your code executes them.
#
# HOW THEY CONNECT TO THE DATABASE:
#   tools.py -> ProblemRepository / TopicRepository (existing layer)
#   Tools NEVER write raw SQL. They use the   existing repositories.
#   This keeps the separation: LLM -> tool -> service/repo -> DB
#
# IMPORTANT: Tools are async because they query the database asynchronously.
#   The agent loop awaits them with: result = await func(db=db, **args)
#
# TOOL SCHEMA (defined at the bottom):
#   This is the dict we send to Gemini so it knows these tools exist.
#   The schema is separate from the implementation — the schema is metadata
#   for the model, the implementation is what your code actually runs.

import json
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.problem import Problem, ProblemStatus, Confidence
from backend.models.topic import Topic
from backend.models.revision import Revision, RevisionStatus
from backend.models.goal import Goal
import google.generativeai as genai
from datetime import date


# =============================================================================
# TOOL 1: get_user_progress
# =============================================================================
# Purpose: Give the LLM an overview of the user overall preparation status.
# When Gemini calls this: user asks "how am I doing?" or "show my progress"
# =============================================================================

async def get_user_progress(db: AsyncSession, user_id: int) -> dict:
    """
    Return overall problem-solving statistics for a user.
    Queries the problems table and counts by status.
    """
    # Count problems by status using a single SQL query
    # We select all active problems for the user, then count in Python.
    # For large datasets, you would use GROUP BY in SQL. For MVP: fine.
    result = await db.execute(
        select(Problem).where(
            Problem.user_id == user_id,
            Problem.is_active == True
        )
    )
    problems = result.scalars().all()

    total = len(problems)
    solved = sum(1 for p in problems if p.status in (
        ProblemStatus.SOLVED.value,
        ProblemStatus.REVISED.value,
        ProblemStatus.MASTERED.value
    ))
    revised = sum(1 for p in problems if p.status in (
        ProblemStatus.REVISED.value,
        ProblemStatus.MASTERED.value
    ))
    mastered = sum(1 for p in problems if p.status == ProblemStatus.MASTERED.value)
    high_confidence = sum(1 for p in problems if p.confidence == Confidence.HIGH.value)

    # Count pending revisions (revision debt)
    rev_result = await db.execute(
        select(Revision).where(
            Revision.user_id == user_id,
            Revision.status == RevisionStatus.PENDING.value,
            Revision.planned_date <= date.today()
        )
    )
    pending_revisions = len(rev_result.scalars().all())

    # Count active goals
    goal_result = await db.execute(
        select(Goal).where(
            Goal.user_id == user_id,
            Goal.status == "ACTIVE"
        )
    )
    active_goals = len(goal_result.scalars().all())

    return {
        "user_id": user_id,
        "total_problems": total,
        "solved": solved,
        "revised": revised,
        "mastered": mastered,
        "high_confidence": high_confidence,
        "solve_rate": round(solved / total, 2) if total > 0 else 0.0,
        "mastery_rate": round(mastered / total, 2) if total > 0 else 0.0,
        "pending_revisions": pending_revisions,
        "active_goals": active_goals,
    }


# =============================================================================
# TOOL 2: get_weak_topics
# =============================================================================
# Purpose: Find topics where the user is struggling.
# When Gemini calls this: "what should I study?", "where am I weak?",
#   "what topics need work?", "what am I failing at?"
# =============================================================================

async def get_weak_topics(db: AsyncSession, user_id: int) -> dict:
    """
    Identify topics where the user has low solve rate or low confidence.
    A topic is considered weak if: solve_rate < 0.5 or mastered_count == 0
    with at least 2 problems attempted.
    """
    # Get all active problems with their topic names
    result = await db.execute(
        select(Problem, Topic.name.label("topic_name"), Topic.id.label("tid"))
        .join(Topic, Problem.topic_id == Topic.id, isouter=True)
        .where(
            Problem.user_id == user_id,
            Problem.is_active == True,
            Problem.topic_id.isnot(None)  # only categorized problems
        )
    )
    rows = result.all()

    # Group by topic in Python
    topic_stats: dict = {}
    for problem, topic_name, topic_id in rows:
        if topic_id not in topic_stats:
            topic_stats[topic_id] = {
                "topic": topic_name,
                "topic_id": topic_id,
                "problem_count": 0,
                "solved_count": 0,
                "mastered_count": 0,
                "high_confidence_count": 0,
            }
        s = topic_stats[topic_id]
        s["problem_count"] += 1
        if problem.status in (
            ProblemStatus.SOLVED.value,
            ProblemStatus.REVISED.value,
            ProblemStatus.MASTERED.value
        ):
            s["solved_count"] += 1
        if problem.status == ProblemStatus.MASTERED.value:
            s["mastered_count"] += 1
        if problem.confidence == Confidence.HIGH.value:
            s["high_confidence_count"] += 1

    # Identify weak topics
    weak = []
    for tid, s in topic_stats.items():
        if s["problem_count"] < 1:
            continue
        solve_rate = s["solved_count"] / s["problem_count"]

        # A topic is weak if:
        # - solve rate under 50%, OR
        # - has problems but nothing mastered
        is_weak = solve_rate < 0.5 or (s["problem_count"] >= 2 and s["mastered_count"] == 0)

        if is_weak:
            reason_parts = []
            if solve_rate < 0.5:
                reason_parts.append(
                    f"only {s['solved_count']} of {s['problem_count']} solved ({int(solve_rate*100)}%)"
                )
            if s["mastered_count"] == 0 and s["problem_count"] >= 2:
                reason_parts.append("no problems mastered yet")

            weak.append({
                "topic": s["topic"],
                "topic_id": s["topic_id"],
                "problem_count": s["problem_count"],
                "solved_count": s["solved_count"],
                "mastered_count": s["mastered_count"],
                "solve_rate": round(solve_rate, 2),
                "reason": "; ".join(reason_parts) if reason_parts else "needs more practice",
            })

    # Sort by solve_rate ascending (weakest first)
    weak.sort(key=lambda x: x["solve_rate"])

    return {"weak_topics": weak, "count": len(weak)}


# =============================================================================
# TOOL DISPATCH TABLE
# =============================================================================
# This is how the agent maps tool names (strings from Gemini) to Python functions.
# When Gemini says: function_call { name: "get_user_progress" }
# The agent does: func = TOOL_FUNCTIONS["get_user_progress"]
#                 result = await func(db=db, **args)
#
# This is intentionally simple. In later stages, you could build a decorator
# system or auto-registry. For Stage 1, explicit is better.
# =============================================================================

TOOL_FUNCTIONS = {
    "get_user_progress": get_user_progress,
    "get_weak_topics": get_weak_topics,
}


# =============================================================================
# TOOL SCHEMA DEFINITIONS
# =============================================================================
# These are the descriptions sent to Gemini so it knows:
#   - what tools exist
#   - what each tool does (description is what the model reads!)
#   - what parameters to provide
#
# CONCEPT: genai.protos.Tool / FunctionDeclaration / Schema
# This is the Gemini SDK format for defining callable functions.
# The "description" field is the most critical - write it clearly.
# The model decides whether to call a tool based on this text.
# =============================================================================

TOOL_SCHEMA = genai.protos.Tool(
    function_declarations=[

        genai.protos.FunctionDeclaration(
            name="get_user_progress",
            description=(
                "Returns overall preparation progress statistics for a user. "
                "Call this when the user asks: how am I doing, what is my progress, "
                "how many problems have I solved, show my stats, or any general "
                "question about their overall preparation status."
            ),
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    "user_id": genai.protos.Schema(
                        type=genai.protos.Type.INTEGER,
                        description="The ID of the user whose progress to fetch"
                    )
                },
                required=["user_id"]
            )
        ),

        genai.protos.FunctionDeclaration(
            name="get_weak_topics",
            description=(
                "Identifies topics where the user is struggling or has low mastery. "
                "Call this when the user asks: what am I weak at, where should I focus, "
                "what topics need work, what are my weakest areas, what should I study next, "
                "or any question about weak areas or study recommendations."
            ),
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    "user_id": genai.protos.Schema(
                        type=genai.protos.Type.INTEGER,
                        description="The ID of the user"
                    )
                },
                required=["user_id"]
            )
        ),

    ]
)

