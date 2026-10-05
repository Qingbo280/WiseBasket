/**
 * DEMO / SYNTHETIC FRONTEND DATA
 *
 * These records exist only to validate the Check Prices prototype. They are
 * not production prices, store data, or a backend response. Keep this file
 * limited to basic store metadata and individual product price records; the
 * calculator derives all ranges, counts, totals, and comparison labels.
 */

export interface DemoStore {
  id: string;
  name: string;
  distanceKm: number;
  address: string;
}

export interface DemoPriceRecord {
  storeId: string;
  productId: string;
  price: number;
}

export interface DemoStorePriceData {
  stores: readonly DemoStore[];
  prices: readonly DemoPriceRecord[];
}

export const DEMO_STORES = [
  {
    id: 'aeon',
    name: 'AEON',
    distanceKm: 1.2,
    address: 'Jalan 1/149, Taman Bukit Angkasa',
  },
  {
    id: 'lotuss',
    name: "Lotus's",
    distanceKm: 2.4,
    address: 'No. 18, Jalan 3/149, Kuala Lumpur',
  },
  {
    id: 'econsave',
    name: 'Econsave',
    distanceKm: 3.1,
    address: 'Jalan Klang Lama, Kuala Lumpur',
  },
] as const satisfies readonly DemoStore[];

/**
 * Coverage intentionally spans the approved Q3 categories. The first five
 * products form the recommended complete recording basket; the remaining
 * products provide partial-coverage and missing-price demo states.
 */
export const DEMO_STORE_PRICE_RECORDS = [
  // Protein and staples used by the recommended happy path.
  { storeId: 'aeon', productId: 'SF002', price: 11.9 },
  { storeId: 'lotuss', productId: 'SF002', price: 11.5 },
  { storeId: 'econsave', productId: 'SF002', price: 12.3 },
  { storeId: 'aeon', productId: 'SF003', price: 18 },
  { storeId: 'lotuss', productId: 'SF003', price: 16.8 },
  { storeId: 'econsave', productId: 'SF003', price: 17.5 },
  { storeId: 'aeon', productId: 'SF001', price: 12 },
  { storeId: 'lotuss', productId: 'SF001', price: 11.8 },
  { storeId: 'econsave', productId: 'SF001', price: 11.9 },
  { storeId: 'aeon', productId: 'SF020', price: 7.2 },
  { storeId: 'lotuss', productId: 'SF020', price: 6.9 },
  { storeId: 'econsave', productId: 'SF020', price: 7 },
  { storeId: 'aeon', productId: 'SF010', price: 3.3 },
  { storeId: 'lotuss', productId: 'SF010', price: 2.8 },
  { storeId: 'econsave', productId: 'SF010', price: 2.5 },

  // Carbs.
  { storeId: 'aeon', productId: 'SF018', price: 6.5 },
  { storeId: 'lotuss', productId: 'SF018', price: 5.9 },
  { storeId: 'econsave', productId: 'SF018', price: 6.2 },
  { storeId: 'aeon', productId: 'SF019', price: 4.5 },
  { storeId: 'lotuss', productId: 'SF019', price: 4.2 },
  { storeId: 'econsave', productId: 'SF019', price: 4.8 },
  { storeId: 'aeon', productId: 'SF036', price: 9.5 },
  { storeId: 'lotuss', productId: 'SF036', price: 8.9 },
  { storeId: 'aeon', productId: 'SF037', price: 6.8 },
  { storeId: 'econsave', productId: 'SF037', price: 7.2 },

  // Protein.
  { storeId: 'aeon', productId: 'SF006', price: 4.2 },
  { storeId: 'lotuss', productId: 'SF006', price: 4 },
  { storeId: 'econsave', productId: 'SF006', price: 4.5 },
  { storeId: 'aeon', productId: 'SF007', price: 5.5 },
  { storeId: 'lotuss', productId: 'SF007', price: 5.2 },
  { storeId: 'econsave', productId: 'SF007', price: 5.8 },

  // Vegetables.
  { storeId: 'aeon', productId: 'SF011', price: 4.9 },
  { storeId: 'lotuss', productId: 'SF011', price: 4.6 },
  { storeId: 'aeon', productId: 'SF012', price: 5.2 },
  { storeId: 'lotuss', productId: 'SF012', price: 4.8 },
  { storeId: 'econsave', productId: 'SF012', price: 5.5 },
  { storeId: 'aeon', productId: 'SF013', price: 4.2 },
  { storeId: 'econsave', productId: 'SF013', price: 4.5 },

  // Fruit.
  { storeId: 'aeon', productId: 'SF016', price: 6.8 },
  { storeId: 'lotuss', productId: 'SF016', price: 6.5 },
  { storeId: 'econsave', productId: 'SF016', price: 7 },
  { storeId: 'aeon', productId: 'SF046', price: 7.5 },
  { storeId: 'lotuss', productId: 'SF046', price: 7 },
  { storeId: 'econsave', productId: 'SF046', price: 7.8 },
  { storeId: 'aeon', productId: 'SF047', price: 9.9 },
  { storeId: 'econsave', productId: 'SF047', price: 10.5 },
  { storeId: 'lotuss', productId: 'SF069', price: 12.5 },
  { storeId: 'econsave', productId: 'SF069', price: 13.2 },

  // Other.
  { storeId: 'aeon', productId: 'SF021', price: 8.9 },
  { storeId: 'lotuss', productId: 'SF021', price: 8.5 },
  { storeId: 'econsave', productId: 'SF021', price: 9.2 },
  { storeId: 'aeon', productId: 'SF031', price: 3.2 },
  { storeId: 'lotuss', productId: 'SF031', price: 3.1 },
] as const satisfies readonly DemoPriceRecord[];

export const DEMO_STORE_PRICE_DATA = {
  stores: DEMO_STORES,
  prices: DEMO_STORE_PRICE_RECORDS,
} as const satisfies DemoStorePriceData;
