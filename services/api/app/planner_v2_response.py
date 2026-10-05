# Convert recipe-first optimizer outcomes into stable API fields.
from packages.optimizer.wisebasket_optimizer.v2.optimizer import OptimizationResult
from services.api.app.schemas import PlannerV2OutcomeResponse


def build_plan_v2_outcome(result: OptimizationResult) -> PlannerV2OutcomeResponse:
    return PlannerV2OutcomeResponse(
        status=result.status,
        requested_meals=result.target_meals,
        supported_meals=result.meal_count,
        deferred_meals=result.shortfall_meals,
        error_codes=list(result.reason_codes),
        minimum_additional_budget_rm=(
            float(result.minimum_additional_budget_rm)
            if result.minimum_additional_budget_rm is not None
            else None
        ),
        estimated_total_cost_rm=float(result.calculation.total_cost_rm),
        missing_price_food_ids=list(result.missing_price_food_ids),
    )
