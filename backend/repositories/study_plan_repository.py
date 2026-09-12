# backend/repositories/study_plan_repository.py
#
# DATA FLOW: create_study_plan tool -> StudyPlanService -> StudyPlanRepository -> DB
# All SQL lives here. No SQL anywhere else in the AI stack.

from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.study_plan import StudyPlan, StudyTask
from backend.schemas.study_plan import LLMStudyPlan


class StudyPlanRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_plan_with_tasks(
        self,
        user_id: int,
        plan_data: LLMStudyPlan,
    ) -> StudyPlan:
        """
        Persist a StudyPlan and all its StudyTasks in one transaction.

        CONCEPT: Why flush() between plan and tasks?
        We flush after creating the plan to get its auto-generated id.
        Then we use that id as plan_id for each task.
        flush() sends the INSERT to the DB but does NOT commit.
        The commit happens in get_db() after the request succeeds.
        If any task fails, the whole transaction rolls back.
        """
        from datetime import date

        plan = StudyPlan(
            user_id=user_id,
            goal_id=plan_data.goal_id,
            title=plan_data.title,
            description=plan_data.description,
            duration_days=plan_data.duration_days,
            daily_hours=plan_data.daily_hours,
            start_date=plan_data.start_date or date.today(),
        )
        self.db.add(plan)
        await self.db.flush()  # get plan.id

        task_objects = []
        for day in plan_data.days:
            for task in day.tasks:
                db_task = StudyTask(
                    plan_id=plan.id,
                    day_number=day.day_number,
                    title=task.title,
                    description=task.description,
                    estimated_minutes=task.estimated_minutes,
                    priority=task.priority,
                    topic_id=task.topic_id,
                )
                self.db.add(db_task)
                task_objects.append(db_task)

        await self.db.flush()

        # Refresh to get server-side defaults (created_at etc.)
        await self.db.refresh(plan)
        return plan

    async def get_by_user(self, user_id: int) -> list[StudyPlan]:
        result = await self.db.execute(
            select(StudyPlan)
            .where(StudyPlan.user_id == user_id)
            .options(selectinload(StudyPlan.tasks))
            .order_by(StudyPlan.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, plan_id: int) -> Optional[StudyPlan]:
        result = await self.db.execute(
            select(StudyPlan)
            .where(StudyPlan.id == plan_id)
            .options(selectinload(StudyPlan.tasks))
        )
        return result.scalar_one_or_none()
