import assert from 'node:assert/strict';
import test from 'node:test';
import { buildNearbyPricesPath, mapNearbyPriceResponse } from './priceCheckApi.ts';

const selectedItem = {
  foodId: 'SF002',
  name: 'Chicken Eggs',
  subtitle: '30 eggs',
  quantityG: 1740,
  imageSource: 1,
  requiresVariantConfirmation: false,
};
const selectedLocation = {
  label: 'Bangsar, Kuala Lumpur',
  latitude: 3.129,
  longitude: 101.679,
};

test('builds a GPS nearby-price request with the selected purchase quantity', () => {
  assert.equal(
    buildNearbyPricesPath('SF002', selectedLocation, 1740),
    '/api/v1/foods/SF002/nearby-prices?latitude=3.129&longitude=101.679&quantity_g=1740&limit=20',
  );
});

test('maps backend stores into comparable frontend results', () => {
  const result = mapNearbyPriceResponse({
    requested_quantity: null,
    requested_unit: null,
    requested_quantity_g: 1740,
    search_mode: 'GPS_RADIUS',
    area_label: null,
    radius_km: 5,
    radius_expanded: false,
    distance_note: null,
    result_status: 'FOUND',
    disclaimer: 'Observed prices only.',
    stores: [{
      store_id: '42',
      store_name: 'Test Market',
      premise_type: 'PASAR BASAH',
      state: 'W.P. Kuala Lumpur',
      district: 'Bangsar',
      address: 'Jalan Test',
      distance_km: 1.25,
      original_unit: '30 biji',
      price_rm_per_100g_purchase: 0.71,
      estimated_total_rm: 12.35,
      last_updated: '2026-09-01',
      price_source: 'PriceCatcher',
    }],
  }, selectedItem, selectedLocation);

  assert.equal(result.status, 'success');
  assert.equal(result.results[0].premiseName, 'Test Market');
  assert.equal(result.results[0].premiseType, 'wet-market');
  assert.equal(result.results[0].price, 12.35);
  assert.equal(result.metadata.bestResultId, '42');
});
