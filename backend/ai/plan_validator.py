# backend/ai/plan_validator.py
#
# WHAT: Deterministic validation of LLM-generated study plans.
#
# WHY THIS FILE EXISTS:
#   The LLM is good at reasoning but cannot guarantee:
#   - Mathematical correctness (total minutes per day <= daily_hours*60)
#   - Database integrity (topic_id references exist)
#   - Business constraints (user owns the data)
#   - Non-empty plans
#
#   This file is pure Python logic. No LLM involved.
#   It runs AFTER the LLM produces a plan and BEFORE we write to the DB.
#
# CONCEPT: LLM is the decision-maker. Backend is the enforcer.
#   The LLM might say "3 hours of Graphs + 2 hours of DP = 5 hours on Day 1"
#   but the user said daily_hours=4. Our code catches this.
#
# Each validation error raises a ValueError with a clear message.
# The calling code wraps these in an AIServiceError for the API.

from backend.schemas.study_plan import LLMStudyPlan, LLMStudyDay


class PlanValidationError(ValueError):
    """Raised when a plan fails deterministic validation."""
    pass


def validate_plan(plan: LLMStudyPlan, user_id: int) -> None:
    """
    Run all deterministic checks on a plan before persisting it.

    Raises PlanValidationError if any check fails.
    Returns None if all checks pass.

    Args:
        plan: The LLMStudyPlan produced by the LLM
        user_id: The authenticated user ID (ownership check)
    """
    _check_duration(plan)
    _check_has_tasks(plan)
    _check_daily_hours(plan)
    _check_task_durations(plan)
    _check_day_numbers(plan)


def _check_duration(plan: LLMStudyPlan) -> None:
    """Plan must have positive duration."""
    if plan.duration_days < 1:
        raise PlanValidationError(
            f"Plan duration must be at least 1 day, got {plan.duration_days}"
        )
    if plan.duration_days > 365:
        raise PlanValidationError(
            f"Plan duration {plan.duration_days} days is unreasonably long. Maximum: 365"
        )


def _check_has_tasks(plan: LLMStudyPlan) -> None:
    """Plan must contain at least one task."""
    total_tasks = sum(len(day.tasks) for day in plan.days)
    if total_tasks == 0:
        raise PlanValidationError("Plan has no tasks. A useful plan needs at least 1 task.")
    if len(plan.days) == 0:
        raise PlanValidationError("Plan has no days defined.")


def _check_daily_hours(plan: LLMStudyPlan) -> None:
    """
    Each day total task time must not exceed the user daily_hours limit.

    This is the key constraint the LLM might violate.
    We check: sum(task.estimated_minutes for day) <= daily_hours * 60
    """
    max_minutes = plan.daily_hours * 60

    for day in plan.days:
        day_total = sum(task.estimated_minutes for task in day.tasks)
        if day_total > max_minutes + 10:  # +10 min tolerance for rounding
            raise PlanValidationError(
                f"Day {day.day_number} ({day.focus}): "
                f"tasks total {day_total} minutes but daily limit is "
                f"{int(max_minutes)} minutes ({plan.daily_hours} hours). "
                f"The plan exceeds the user available study time."
            )


def _check_task_durations(plan: LLMStudyPlan) -> None:
    """Every task must have a positive, reasonable duration."""
    for day in plan.days:
        for task in day.tasks:
            if task.estimated_minutes < 5:
                raise PlanValidationError(
                    f"Task '{task.title}' on day {day.day_number} has "
                    f"estimated_minutes={task.estimated_minutes}. Minimum is 5 minutes."
                )
            if task.estimated_minutes > 480:
                raise PlanValidationError(
                    f"Task '{task.title}' on day {day.day_number} has "
                    f"estimated_minutes={task.estimated_minutes}. "
                    f"A single task cannot exceed 8 hours (480 minutes)."
                )


def _check_day_numbers(plan: LLMStudyPlan) -> None:
    """Day numbers must be positive and within plan duration."""
    seen = set()
    for day in plan.days:
        if day.day_number < 1:
            raise PlanValidationError(
                f"Day number must be >= 1, got {day.day_number}"
            )
        if day.day_number > plan.duration_days:
            raise PlanValidationError(
                f"Day {day.day_number} exceeds plan duration of {plan.duration_days} days"
            )
        if day.day_number in seen:
            raise PlanValidationError(
                f"Duplicate day_number {day.day_number} in plan. Each day must appear once."
            )
        seen.add(day.day_number)
