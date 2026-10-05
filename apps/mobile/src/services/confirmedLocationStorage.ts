import AsyncStorage from '@react-native-async-storage/async-storage';
import {
  normalizeStoredConfirmedLocation,
  type ConfirmedLocation,
} from './confirmedLocationContent';

const CONFIRMED_LOCATION_KEY = 'wisebasket.mobile.confirmedShoppingLocation';
const RECENT_LOCATIONS_KEY = 'wisebasket.mobile.recentShoppingLocations';
const MAX_RECENT_LOCATIONS = 3;

function recentLocationIdentity(location: ConfirmedLocation): string {
  const label = (location.shortLabel || location.address).trim().toLocaleLowerCase();
  return label || `${location.latitude ?? ''}:${location.longitude ?? ''}`;
}

function normalizeRecentLocations(value: unknown): ConfirmedLocation[] {
  if (!Array.isArray(value)) return [];

  const seen = new Set<string>();
  return value
    .map(normalizeStoredConfirmedLocation)
    .filter((location): location is ConfirmedLocation => {
      if (!location) return false;
      const identity = recentLocationIdentity(location);
      if (seen.has(identity)) return false;
      seen.add(identity);
      return true;
    })
    .slice(0, MAX_RECENT_LOCATIONS);
}

export async function loadConfirmedLocation(): Promise<ConfirmedLocation | null> {
  try {
    const stored = await AsyncStorage.getItem(CONFIRMED_LOCATION_KEY);
    if (!stored) return null;
    return normalizeStoredConfirmedLocation(JSON.parse(stored));
  } catch {
    return null;
  }
}

export async function saveConfirmedLocation(location: ConfirmedLocation): Promise<void> {
  await AsyncStorage.setItem(CONFIRMED_LOCATION_KEY, JSON.stringify(location));
}

/** Returns null only when no recent-location history has been initialized. */
export async function loadRecentLocations(): Promise<ConfirmedLocation[] | null> {
  try {
    const stored = await AsyncStorage.getItem(RECENT_LOCATIONS_KEY);
    if (stored === null) return null;
    return normalizeRecentLocations(JSON.parse(stored));
  } catch {
    return null;
  }
}

export async function saveRecentLocation(location: ConfirmedLocation): Promise<ConfirmedLocation[]> {
  const current = await loadRecentLocations() ?? [];
  const identity = recentLocationIdentity(location);
  const next = normalizeRecentLocations([
    location,
    ...current.filter((entry) => recentLocationIdentity(entry) !== identity),
  ]);
  await AsyncStorage.setItem(RECENT_LOCATIONS_KEY, JSON.stringify(next));
  return next;
}

export async function clearRecentLocations(): Promise<void> {
  // Keep an empty list as an initialized value so startup does not seed it
  // again from the current confirmed location.
  await AsyncStorage.setItem(RECENT_LOCATIONS_KEY, '[]');
}
