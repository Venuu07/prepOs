# backend/ai/tools.py
#
# Stage 2 extension of Stage 1 tools.
#
# Stage 1 tools (read-only):
#   get_user_progress   - overall stats
#   get_weak_topics     - topics with low solve rate
#
# Stage 2 additions (read-only):
#   get_goals           - user preparation goals with deadlines
#   get_pending_revisions - overdue revision debt
#
# Stage 2 write tool:
#   create_study_plan   - validate + persist an LLM-generated plan
#
# IMPORTANT DISTINCTION:
#   Read tools: fetch data -> return dict -> no side effects
#   Write tools: receive structured data -> validate -> write to DB -> return result
#
# The TOOL_FUNCTIONS dict is the dispatch table.
# The TOOL_SCHEMA is the metadata sent to Gemini.
# These are separate intentionally: implementation vs contract.

import json
import logging
from datetime import date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import google.generativeai as genai

from backend.models.problem import Problem, ProblemStatus, Confidence
from backend.models.topic import Topic
from backend.models.revision import Revision, RevisionStatus
from backend.models.goal import Goal
from backend.schemas.study_plan import LLMStudyPlan
from backend.services.study_plan_service import StudyPlanService
from backend.core.exceptions import AIServiceError, ValidationError

logger = logging.getLogger(__name__)


# =============================================================================
# READ TOOL 1: get_user_progress (from Stage 1, unchanged)
# =============================================================================

async def get_user_progress(db: AsyncSession, user_id: int) -> dict:
    """Return overall problem-solving statistics for a user."""
    result = await db.execute(
        select(Problem).where(Problem.user_id == user_id, Problem.is_active == True)
    )
    problems = result.scalars().all()

    total = len(problems)
    solved = sum(1 for p in problems if p.status in (
        ProblemStatus.SOLVED.value, ProblemStatus.REVISED.value, ProblemStatus.MASTERED.value
    ))
    revised = sum(1 for p in problems if p.status in (
        ProblemStatus.REVISED.value, ProblemStatus.MASTERED.value
    ))
    mastered = sum(1 for p in problems if p.status == ProblemStatus.MASTERED.value)

    rev_result = await db.execute(
        select(Revision).where(
            Revision.user_id == user_id,
            Revision.status == RevisionStatus.PENDING.value,
            Revision.planned_date <= date.today()
        )
    )
    pending_revisions = len(rev_result.scalars().all())

    goal_result = await db.execute(
        select(Goal).where(Goal.user_id == user_id, Goal.status == "ACTIVE")
    )
    active_goals = len(goal_result.scalars().all())

    return {
        "user_id": user_id,
        "total_problems": total,
        "solved": solved,
        "revised": revised,
        "mastered": mastered,
        "solve_rate": round(solved / total, 2) if total > 0 else 0.0,
        "mastery_rate": round(mastered / total, 2) if total > 0 else 0.0,
        "pending_revisions": pending_revisions,
        "active_goals": active_goals,
    }


# =============================================================================
# READ TOOL 2: get_weak_topics (from Stage 1, unchanged)
# =============================================================================

async def get_weak_topics(db: AsyncSession, user_id: int) -> dict:
    """Identify topics where the user has low solve rate or low confidence."""
    result = await db.execute(
        select(Problem, Topic.name.label("topic_name"), Topic.id.label("tid"))
        .join(Topic, Problem.topic_id == Topic.id, isouter=True)
        .where(
            Problem.user_id == user_id,
            Problem.is_active == True,
            Problem.topic_id.isnot(None)
        )
    )
    rows = result.all()

    topic_stats: dict = {}
    for problem, topic_name, topic_id in rows:
        if topic_id not in topic_stats:
            topic_stats[topic_id] = {
                "topic": topic_name, "topic_id": topic_id,
                "problem_count": 0, "solved_count": 0, "mastered_count": 0,
            }
        s = topic_stats[topic_id]
        s["problem_count"] += 1
        if problem.status in (ProblemStatus.SOLVED.value, ProblemStatus.REVISED.value, ProblemStatus.MASTERED.value):
            s["solved_count"] += 1
        if problem.status == ProblemStatus.MASTERED.value:
            s["mastered_count"] += 1

    weak = []
    for tid, s in topic_stats.items():
        if s["problem_count"] < 1:
            continue
        solve_rate = s["solved_count"] / s["problem_count"]
        is_weak = solve_rate < 0.5 or (s["problem_count"] >= 2 and s["mastered_count"] == 0)
        if is_weak:
            reason_parts = []
            if solve_rate < 0.5:
                reason_parts.append(f"only {s['solved_count']}/{s['problem_count']} solved ({int(solve_rate*100)}%)")
            if s["mastered_count"] == 0 and s["problem_count"] >= 2:
                reason_parts.append("no problems mastered yet")
            weak.append({
                "topic": s["topic"], "topic_id": s["topic_id"],
                "problem_count": s["problem_count"], "solved_count": s["solved_count"],
                "mastered_count": s["mastered_count"], "solve_rate": round(solve_rate, 2),
                "reason": "; ".join(reason_parts) if reason_parts else "needs more practice",
            })

    weak.sort(key=lambda x: x["solve_rate"])
    return {"weak_topics": weak, "count": len(weak)}


# =============================================================================
# READ TOOL 3: get_goals (Stage 2 addition)
# =============================================================================

async def get_goals(db: AsyncSession, user_id: int) -> dict:
    """
    Return active preparation goals for a user, with days remaining to deadline.
    The agent uses this to understand urgency and prioritize topics accordingly.
    """
    result = await db.execute(
        select(Goal)
        .where(Goal.user_id == user_id, Goal.status == "ACTIVE")
        .order_by(Goal.target_date.asc().nulls_last())
    )
    goals = result.scalars().all()

    today = date.today()
    goals_data = []
    for g in goals:
        days_remaining = None
        if g.target_date:
            days_remaining = (g.target_date - today).days

        goals_data.append({
            "id": g.id,
            "title": g.title,
            "goal_type": g.goal_type,
            "priority": g.priority,
            "target_date": g.target_date.isoformat() if g.target_date else None,
            "days_remaining": days_remaining,
            "description": g.description,
        })

    return {"goals": goals_data, "count": len(goals_data)}


# =============================================================================
# READ TOOL 4: get_pending_revisions (Stage 2 addition)
# =============================================================================

async def get_pending_revisions(db: AsyncSession, user_id: int) -> dict:
    """
    Return overdue revisions (planned_date <= today and still PENDING).
    This is the revision debt signal. The agent should incorporate these
    into a plan so the user catches up on missed revisions.
    """
    today = date.today()
    result = await db.execute(
        select(Revision, Topic.name.label("topic_name"))
        .join(Topic, Revision.topic_id == Topic.id)
        .where(
            Revision.user_id == user_id,
            Revision.status == RevisionStatus.PENDING.value,
            Revision.planned_date <= today,
        )
        .order_by(Revision.planned_date.asc())
    )
    rows = result.all()

    revisions_data = []
    for rev, topic_name in rows:
        days_overdue = (today - rev.planned_date).days
        revisions_data.append({
            "id": rev.id,
            "topic_id": rev.topic_id,
            "topic": topic_name,
            "planned_date": rev.planned_date.isoformat(),
            "days_overdue": days_overdue,
        })

    return {"pending_revisions": revisions_data, "count": len(revisions_data)}


# =============================================================================
# WRITE TOOL: create_study_plan (Stage 2 - the key new capability)
# =============================================================================
# CONCEPT: This is a write tool. It differs from read tools because:
#   1. It receives structured input from the LLM (the plan JSON)
#   2. It validates the input (Pydantic + business rules)
#   3. It writes to the database (study_plans + study_tasks tables)
#   4. On failure, it raises an exception → the DB transaction rolls back
#
# The LLM provides the plan data as tool arguments.
# We parse + validate it before any DB write.
# If validation fails, we return an error to the LLM so it can correct.
# =============================================================================

async def create_study_plan(
    db: AsyncSession,
    user_id: int,
    title: str,
    duration_days: int,
    daily_hours: float,
    days: list,
    goal_id: int = None,
    start_date: str = None,
    description: str = None,
) -> dict:
    """
    Validate and persist a study plan generated by the LLM.

    This function is the adapter between the LLM and the service layer.
    It converts the raw tool arguments into a typed LLMStudyPlan,
    then delegates to StudyPlanService for validation and persistence.
    """
    # Step 1: Parse raw args into typed Pydantic schema
    # This gives us Pydantic validation for free (field types, required fields, ranges)
    try:
        parsed_start = None
        if start_date:
            from datetime import date as _date
            parsed_start = _date.fromisoformat(start_date)

        plan_schema = LLMStudyPlan(
            title=title,
            duration_days=duration_days,
            daily_hours=daily_hours,
            goal_id=goal_id,
            start_date=parsed_start,
            description=description,
            days=days,
        )
    except Exception as e:
        # Return error to LLM so it can correct its output
        return {
            "success": False,
            "error": f"Plan schema validation failed: {str(e)}",
            "hint": "Ensure all required fields are present and types are correct.",
        }

    # Step 2: Business validation + DB write via service
    service = StudyPlanService(db)
    try:
        plan = await service.create_from_llm(user_id=user_id, plan_data=plan_schema)
    except ValidationError as e:
        # Business validation failed - return error to LLM
        return {
            "success": False,
            "error": f"Plan validation failed: {e.message}",
            "hint": "Adjust the plan to fit within the user daily hours limit.",
        }
    except Exception as e:
        logger.error(f"Unexpected error creating plan: {e}", exc_info=True)
        return {
            "success": False,
            "error": "Failed to save the plan due to an internal error.",
        }
    
    
    # Step 3: Return success with plan summary
    total_tasks = sum(len(day["tasks"]) for day in days)
    return {
        "success": True,
        "plan_id": plan.id,
        "title": plan.title,
        "duration_days": plan.duration_days,
        "daily_hours": plan.daily_hours,
        "tasks_created": total_tasks,
        "message": f"Study plan created successfully with {total_tasks} tasks across {duration_days} days.",
    }


# =============================================================================
# TOOL DISPATCH TABLE
# Maps tool names (strings from Gemini) to Python functions.
# NEVER execute a function not in this table.
# =============================================================================

TOOL_FUNCTIONS = {
    # Read tools
    "get_user_progress": get_user_progress,
    "get_weak_topics": get_weak_topics,
    "get_goals": get_goals,
    "get_pending_revisions": get_pending_revisions,
    # Write tool
    "create_study_plan": create_study_plan,
}

# =============================================================================
# TOOL SCHEMA DEFINITIONS
# Sent to Gemini so it knows what tools exist and when to use them.
# =============================================================================

TOOL_SCHEMA = genai.protos.Tool(
    function_declarations=[

        genai.protos.FunctionDeclaration(
            name="get_user_progress",
            description=(
                "Returns overall preparation statistics: total problems, solve rate, mastery rate, "
                "pending revisions, active goals. Call this first when the user asks about their "
                "progress or when creating a plan to understand their baseline."
            ),
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={"user_id": genai.protos.Schema(type=genai.protos.Type.INTEGER, description="User ID")},
                required=["user_id"]
            )
        ),

        genai.protos.FunctionDeclaration(
            name="get_weak_topics",
            description=(
                "Identifies topics where the user struggles (low solve rate or no mastered problems). "
                "Call this when creating a plan or when the user asks what to focus on. "
                "Returns topics sorted weakest-first with solve rates."
            ),
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={"user_id": genai.protos.Schema(type=genai.protos.Type.INTEGER, description="User ID")},
                required=["user_id"]
            )
        ),

        genai.protos.FunctionDeclaration(
            name="get_goals",
            description=(
                "Returns the user active preparation goals with their deadlines and days remaining. "
                "Call this when creating a plan to understand urgency and time constraints. "
                "Essential for time-sensitive planning (e.g. interview in 7 days)."
            ),
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={"user_id": genai.protos.Schema(type=genai.protos.Type.INTEGER, description="User ID")},
                required=["user_id"]
            )
        ),

        genai.protos.FunctionDeclaration(
            name="get_pending_revisions",
            description=(
                "Returns overdue revision sessions (topics that were scheduled for revision but not done). "
                "Call this when creating a plan to incorporate revision debt. "
                "These should be included in the plan so the user catches up."
            ),
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={"user_id": genai.protos.Schema(type=genai.protos.Type.INTEGER, description="User ID")},
                required=["user_id"]
            )
        ),

        genai.protos.FunctionDeclaration(
            name="create_study_plan",
            description=(
                "Creates and persists a structured study plan in the database. "
                "Call this ONLY after fetching user progress, weak topics, goals, and revisions. "
                "The plan must fit within the user daily hours. "
                "Each day tasks total estimated_minutes must not exceed daily_hours * 60."
            ),
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    "user_id": genai.protos.Schema(type=genai.protos.Type.INTEGER, description="User ID"),
                    "title": genai.protos.Schema(type=genai.protos.Type.STRING, description="Plan title, e.g. '7-Day Interview Prep'"),
                    "duration_days": genai.protos.Schema(type=genai.protos.Type.INTEGER, description="Number of days the plan covers"),
                    "daily_hours": genai.protos.Schema(type=genai.protos.Type.NUMBER, description="Hours available per day for study"),
                    "goal_id": genai.protos.Schema(type=genai.protos.Type.INTEGER, description="Optional: ID of the goal this plan serves"),
                    "start_date": genai.protos.Schema(type=genai.protos.Type.STRING, description="Optional: start date in YYYY-MM-DD format"),
                    "description": genai.protos.Schema(type=genai.protos.Type.STRING, description="Optional: brief plan description"),
                    "days": genai.protos.Schema(
                        type=genai.protos.Type.ARRAY,
                        description="List of study days",
                        items=genai.protos.Schema(
                            type=genai.protos.Type.OBJECT,
                            properties={
                                "day_number": genai.protos.Schema(type=genai.protos.Type.INTEGER, description="Day number, starting from 1"),
                                "focus": genai.protos.Schema(type=genai.protos.Type.STRING, description="Main topic focus for this day"),
                                "tasks": genai.protos.Schema(
                                    type=genai.protos.Type.ARRAY,
                                    description="List of tasks for this day",
                                    items=genai.protos.Schema(
                                        type=genai.protos.Type.OBJECT,
                                        properties={
                                            "title": genai.protos.Schema(type=genai.protos.Type.STRING, description="Task title"),
                                            "estimated_minutes": genai.protos.Schema(type=genai.protos.Type.INTEGER, description="Estimated minutes to complete"),
                                            "priority": genai.protos.Schema(type=genai.protos.Type.STRING, description="HIGH, MEDIUM, or LOW"),
                                            "topic_id": genai.protos.Schema(type=genai.protos.Type.INTEGER, description="Optional topic ID if known"),
                                            "description": genai.protos.Schema(type=genai.protos.Type.STRING, description="Optional task description"),
                                        },
                                        required=["title", "estimated_minutes"]
                                    )
                                )
                            },
                            required=["day_number", "focus", "tasks"]
                        )
                    ),
                },
                required=["user_id", "title", "duration_days", "daily_hours", "days"]
            )
        ),

    ]
)
