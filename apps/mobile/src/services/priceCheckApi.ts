import type { FoodPriceUnit } from '../api/plannerTypes';
import type { PriceCheckSelectedItem } from '../screens/priceCheckItemVariantConfirmationContent';
import type {
  PriceCheckPremiseType,
  PriceCheckResultsData,
  PriceCheckSelectedLocation,
  PriceCheckSelectedVariant,
} from '../screens/priceCheckResultsContent';
import type { PriceCheckStoreDetailsData } from '../screens/priceCheckStoreDetailsContent';

interface BackendNearbyPriceStore {
  store_id: string;
  store_name: string;
  premise_type: string | null;
  state: string | null;
  district: string | null;
  address: string | null;
  distance_km: number | null;
  original_unit: string | null;
  price_rm_per_100g_purchase: number;
  estimated_total_rm: number;
  last_updated: string;
  price_source: string;
}

interface BackendNearbyPriceResponse {
  requested_quantity: number | null;
  requested_unit: string | null;
  requested_quantity_g: number;
  search_mode: 'GPS_RADIUS' | 'MANUAL_AREA';
  area_label: string | null;
  radius_km: number | null;
  radius_expanded: boolean;
  distance_note: string | null;
  result_status: 'FOUND' | 'NO_PRICE_IN_RADIUS' | 'NO_PRICE_IN_AREA';
  disclaimer: string;
  stores: BackendNearbyPriceStore[];
}

const PRICE_CHECK_TIMEOUT_MS = 15_000;

export async function fetchPriceCheckUnits(foodId: string): Promise<FoodPriceUnit[]> {
  const { apiRequest } = await import('./api');
  return apiRequest<FoodPriceUnit[]>(
    `/api/v1/foods/${encodeURIComponent(foodId)}/price-units`,
    { auth: false, method: 'GET', timeoutMs: PRICE_CHECK_TIMEOUT_MS },
  );
}

function premiseType(value: string | null): PriceCheckPremiseType {
  const normalized = value?.trim().toLowerCase().replace(/[ _]+/g, '-');
  if (normalized === 'minimarket' || normalized === 'mini-market') return 'minimarket';
  if (normalized === 'wet-market' || normalized === 'pasar-basah') return 'wet-market';
  if (normalized === 'hypermarket') return 'hypermarket';
  if (normalized === 'supermarket') return 'supermarket';
  return 'other';
}

export function buildNearbyPricesPath(
  foodId: string,
  location: PriceCheckSelectedLocation,
  quantityG?: number,
): string {
  const params: string[] = [];
  if (location.latitude !== null && location.longitude !== null) {
    params.push(`latitude=${encodeURIComponent(location.latitude)}`);
    params.push(`longitude=${encodeURIComponent(location.longitude)}`);
  } else if (location.state) {
    params.push(`state=${encodeURIComponent(location.state)}`);
    if (location.district) params.push(`district=${encodeURIComponent(location.district)}`);
  } else {
    throw new Error('Select a valid location before checking prices.');
  }
  if (quantityG && Number.isFinite(quantityG)) {
    params.push(`quantity_g=${encodeURIComponent(quantityG)}`);
  }
  params.push('limit=20');
  return `/api/v1/foods/${encodeURIComponent(foodId)}/nearby-prices?${params.join('&')}`;
}

export function mapNearbyPriceResponse(
  response: BackendNearbyPriceResponse,
  selectedItem: PriceCheckSelectedItem,
  selectedLocation: PriceCheckSelectedLocation,
  selectedVariant?: PriceCheckSelectedVariant,
): PriceCheckResultsData {
  if (response.result_status !== 'FOUND' || response.stores.length === 0) {
    return {
      status: 'empty',
      selectedItem,
      selectedLocation,
      selectedVariant,
      message: response.distance_note ?? 'No recent PriceCatcher prices were found for this item nearby.',
    };
  }

  const packLabel = selectedItem.subtitle ?? `${response.requested_quantity_g} g`;
  const results = response.stores.map((store) => ({
    premiseId: store.store_id,
    premiseName: store.store_name,
    premiseType: premiseType(store.premise_type),
    address: store.address ?? undefined,
    distanceKm: store.distance_km,
    price: store.estimated_total_rm,
    currency: 'RM',
    retailUnit: store.original_unit ?? undefined,
    packLabel,
    normalizedPrice: store.price_rm_per_100g_purchase,
    normalizedUnit: '100 g',
    priceDate: store.last_updated,
  }));
  const updatedDate = response.stores
    .map((store) => store.last_updated)
    .filter(Boolean)
    .sort()
    .at(-1) ?? null;
  const bestPrice = results[0]?.price;
  const comparisonBaseline = typeof bestPrice === 'number'
    ? results
      .slice(1)
      .map((result) => result.price)
      .filter((price) => Number.isFinite(price) && price > bestPrice)
      .sort((left, right) => left - right)[0] ?? null
    : null;

  return {
    status: 'success',
    selectedItem,
    selectedLocation,
    selectedVariant,
    results,
    metadata: {
      dataSource: response.stores[0]?.price_source || 'PriceCatcher',
      updatedDate,
      resultCount: results.length,
      pricesComparable: true,
      comparisonBaseline,
      bestResultId: results[0]?.premiseId,
      summaryBanner: {
        claim: 'lower-price',
        message: 'Lower price found nearby!',
        supportingCopy: 'Compare prices and choose what works for you.',
        tone: 'success',
      },
    },
  };
}

export async function getNearbyFoodPrices(
  selectedItem: PriceCheckSelectedItem,
  selectedLocation: PriceCheckSelectedLocation,
  selectedVariant?: PriceCheckSelectedVariant,
): Promise<PriceCheckResultsData> {
  const { apiRequest } = await import('./api');
  const response = await apiRequest<BackendNearbyPriceResponse>(
    buildNearbyPricesPath(
      selectedItem.foodId,
      selectedLocation,
      selectedVariant?.quantityG ?? selectedItem.quantityG,
    ),
    { auth: false, method: 'GET' },
  );
  return mapNearbyPriceResponse(response, selectedItem, selectedLocation, selectedVariant);
}

export function createStoreDetailsFromPriceResult(
  data: Extract<PriceCheckResultsData, { status: 'success' }>,
  premiseId: string,
): PriceCheckStoreDetailsData | null {
  const selectedPriceResult = data.results.find((result) => result.premiseId === premiseId);
  if (!selectedPriceResult) return null;
  return {
    selectedItem: data.selectedItem,
    selectedLocation: data.selectedLocation,
    selectedVariant: data.selectedVariant,
    selectedPriceResult,
    metadata: {
      dataSource: data.metadata.dataSource,
      updatedDate: selectedPriceResult.priceDate ?? data.metadata.updatedDate,
      note: 'Observed PriceCatcher price; not a live stock or checkout guarantee.',
    },
  };
}
