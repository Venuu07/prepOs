# tests/test_stage2.py
# Stage 2 tests: plan validation (pure Python, no DB, no LLM required)

import pytest
import pydantic
from backend.ai.plan_validator import validate_plan, PlanValidationError
from backend.schemas.study_plan import LLMStudyPlan, LLMStudyDay, LLMStudyTask


def make_task(**kw) -> LLMStudyTask:
    defaults = {"title": "Test task", "estimated_minutes": 60, "priority": "MEDIUM"}
    defaults.update(kw)
    return LLMStudyTask(**defaults)


def make_day(day_number=1, focus="Graphs", minutes_per_task=60, num_tasks=3) -> LLMStudyDay:
    return LLMStudyDay(
        day_number=day_number,
        focus=focus,
        tasks=[make_task(estimated_minutes=minutes_per_task) for _ in range(num_tasks)]
    )


def make_plan(**overrides) -> LLMStudyPlan:
    defaults = {
        "title": "Test Plan",
        "duration_days": 3,
        "daily_hours": 3.0,
        "days": [
            make_day(day_number=1, focus="Graphs"),   # 3 * 60 = 180 min = 3h exactly
            make_day(day_number=2, focus="DP"),
        ]
    }
    defaults.update(overrides)
    return LLMStudyPlan(**defaults)


# ── Test 1: Valid plan passes ─────────────────────────────────────────────────

def test_valid_plan_passes():
    """Correctly structured plan passes without raising."""
    validate_plan(make_plan(), user_id=1)


# ── Test 2: Exceeding daily hours fails ───────────────────────────────────────

def test_plan_exceeding_daily_hours_fails():
    """Tasks exceeding daily_hours must be rejected."""
    plan = make_plan(
        daily_hours=2.0,  # 120 min max
        days=[
            LLMStudyDay(
                day_number=1, focus="Overload",
                tasks=[
                    make_task(estimated_minutes=70),
                    make_task(estimated_minutes=70),  # total 140 > 120+10 tolerance
                ]
            )
        ]
    )
    with pytest.raises(PlanValidationError) as exc_info:
        validate_plan(plan, user_id=1)
    assert "limit" in str(exc_info.value).lower() or "exceed" in str(exc_info.value).lower()


# ── Test 3: Empty tasks list fails Pydantic ───────────────────────────────────

def test_empty_tasks_pydantic_rejects():
    """LLMStudyDay with tasks=[] fails at Pydantic (min_length=1)."""
    with pytest.raises(pydantic.ValidationError):
        LLMStudyDay(day_number=1, focus="Nothing", tasks=[])


# ── Test 4: Zero duration fails Pydantic ─────────────────────────────────────

def test_zero_duration_fails():
    """duration_days=0 fails at Pydantic (ge=1)."""
    with pytest.raises(pydantic.ValidationError):
        LLMStudyPlan(title="x", duration_days=0, daily_hours=3.0, days=[make_day()])


# ── Test 5: Day number > duration fails Pydantic validator ───────────────────

def test_day_exceeds_duration():
    """Day 5 in a 3-day plan fails at Pydantic field_validator."""
    with pytest.raises(pydantic.ValidationError) as exc_info:
        LLMStudyPlan(
            title="x", duration_days=3, daily_hours=3.0,
            days=[LLMStudyDay(day_number=5, focus="X", tasks=[make_task()])]
        )
    assert "duration_days" in str(exc_info.value) or "5" in str(exc_info.value)


# ── Test 6: Duplicate day numbers fail our validator ─────────────────────────

def test_duplicate_day_numbers():
    """Two entries for day 1 must be rejected by validate_plan."""
    plan = make_plan(
        days=[
            make_day(day_number=1, focus="A"),
            make_day(day_number=1, focus="B"),  # duplicate
        ]
    )
    with pytest.raises(PlanValidationError) as exc_info:
        validate_plan(plan, user_id=1)
    assert "duplicate" in str(exc_info.value).lower()


# ── Test 7: Task below minimum minutes fails Pydantic ────────────────────────

def test_task_below_min_minutes():
    """estimated_minutes < 5 fails Pydantic (ge=5)."""
    with pytest.raises(pydantic.ValidationError):
        LLMStudyTask(title="x", estimated_minutes=1, priority="HIGH")


# ── Test 8: Invalid priority fails Pydantic ──────────────────────────────────

def test_invalid_priority():
    """priority must match HIGH|MEDIUM|LOW."""
    with pytest.raises(pydantic.ValidationError):
        LLMStudyTask(title="x", estimated_minutes=60, priority="URGENT")


# ── Test 9: No unknown tools in dispatch ─────────────────────────────────────

def test_no_unknown_tools_in_dispatch():
    """Dispatch table must only contain known, approved tools."""
    from backend.ai.tools import TOOL_FUNCTIONS
    allowed = {"get_user_progress", "get_weak_topics", "get_goals",
               "get_pending_revisions", "create_study_plan"}
    for name in TOOL_FUNCTIONS:
        assert name in allowed, f"Unexpected tool in dispatch: {name}"


# ── Test 10: All expected tools present ──────────────────────────────────────

def test_all_stage2_tools_present():
    """All Stage 2 tools must be registered."""
    from backend.ai.tools import TOOL_FUNCTIONS
    for tool in ["get_user_progress", "get_weak_topics", "get_goals",
                 "get_pending_revisions", "create_study_plan"]:
        assert tool in TOOL_FUNCTIONS, f"Missing tool: {tool}"
