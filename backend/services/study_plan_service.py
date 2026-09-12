# backend/services/study_plan_service.py
#
# WHAT: Business logic for creating and reading study plans.
# ROLE IN ARCHITECTURE: ai tool -> StudyPlanService -> StudyPlanRepository -> DB
#
# The service is the gatekeeper. It:
#   1. Runs deterministic validation (via plan_validator)
#   2. Delegates DB writes to the repository
#   3. Returns structured data the tool can serialize back to the LLM

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.study_plan import StudyPlan
from backend.repositories.study_plan_repository import StudyPlanRepository
from backend.schemas.study_plan import LLMStudyPlan
from backend.ai.plan_validator import validate_plan, PlanValidationError
from backend.core.exceptions import ValidationError as PrepOSValidationError


class StudyPlanService:

    def __init__(self, db: AsyncSession):
        self.repo = StudyPlanRepository(db)

    async def create_from_llm(
        self,
        user_id: int,
        plan_data: LLMStudyPlan,
    ) -> StudyPlan:

        """
        Validate and persist an LLM-generated study plan.

        Flow:
          1. Pydantic already validated shape (in LLMStudyPlan)
          2. We run deterministic business validation
          3. If valid, delegate to repository for DB write
          4. Return the created plan

        Raises PrepOSValidationError if validation fails.
        The DB transaction is NOT committed here — it commits in get_db().
        If an exception is raised, get_db() rolls back automatically.
        """
        try:
            validate_plan(plan_data, user_id)
        except PlanValidationError as e:
            raise PrepOSValidationError(str(e))

        return await self.repo.create_plan_with_tasks(user_id, plan_data)

    async def get_user_plans(self, user_id: int) -> list[StudyPlan]:
        return await self.repo.get_by_user(user_id)
