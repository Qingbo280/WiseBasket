# Dependency-injected HTTP boundary for the recipe-first planner.
from typing import Protocol

from fastapi import APIRouter, HTTPException, status

from services.api.app.planner_v2_service import (
    CatalogValidationError,
    PlannerV2Catalog,
    create_plan_v2,
)
from services.api.app.schemas import PlannerV2CreateRequest, PlannerV2PlanResponse


class CatalogUnavailableError(RuntimeError):
    pass


class PlannerV2CatalogProvider(Protocol):
    async def get_catalog(self, payload: PlannerV2CreateRequest) -> PlannerV2Catalog:
        ...


def create_planner_v2_router(provider: PlannerV2CatalogProvider) -> APIRouter:
    router = APIRouter()

    @router.post("/api/v2/plans", response_model=PlannerV2PlanResponse)
    async def create_recipe_first_plan(
        payload: PlannerV2CreateRequest,
    ) -> PlannerV2PlanResponse:
        try:
            catalog = await provider.get_catalog(payload)
        except CatalogUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "PLANNER_V2_CATALOG_UNAVAILABLE",
                    "message": str(error),
                },
            ) from error
        try:
            return create_plan_v2(payload, catalog)
        except CatalogValidationError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "PLANNER_V2_CATALOG_INVALID",
                    "message": "Planner catalogue failed validation",
                    "issues": list(error.issues),
                },
            ) from error

    return router
