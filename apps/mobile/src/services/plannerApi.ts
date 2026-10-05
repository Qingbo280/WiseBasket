import type { FoodInfo, PlanRequest, PlanResponse } from '../api/plannerTypes';
import { apiRequest } from './api';
import {
  adaptPlannerV2Response,
  toPlannerV2Request,
  type PlannerV2Response,
} from './plannerV2Adapter';

const CATALOG_TIMEOUT_MS = 90_000;
const PLAN_TIMEOUT_MS = 90_000;

/** Live food catalogue. The backend only serves ACTIVE, catalogue-eligible
 *  foods by default (the catalog_eligible tag hides curated-out foods), so
 *  whatever comes back here is exactly what the planning layer may pick.
 *  `includeHidden` additionally fetches the catalog_eligible=false foods for
 *  the what-you-have/pantry layer: users can buy them in a real shop even
 *  though we have no trustworthy price, so they may be recorded as stock
 *  but never planned. */
export async function fetchFoodCatalog(options?: {
  includeHidden?: boolean;
  includeMinPurchasePrice?: boolean;
}): Promise<FoodInfo[]> {
  const params = new URLSearchParams();
  if (options?.includeHidden) params.set('include_hidden', 'true');
  if (options?.includeMinPurchasePrice) params.set('include_min_purchase_price', 'true');
  const query = params.size > 0 ? `?${params.toString()}` : '';
  return apiRequest<FoodInfo[]>(`/api/v1/foods${query}`, {
    auth: false,
    method: 'GET',
    timeoutMs: CATALOG_TIMEOUT_MS,
  });
}

export async function createPlan(
  request: PlanRequest,
  catalogFoods: readonly FoodInfo[] = [],
): Promise<PlanResponse> {
  const response = await apiRequest<PlannerV2Response>('/api/v2/plans', {
    auth: true,
    body: toPlannerV2Request(request),
    errorScope: 'plan',
    timeoutMs: PLAN_TIMEOUT_MS,
  });
  return adaptPlannerV2Response(response, request, catalogFoods);
}
