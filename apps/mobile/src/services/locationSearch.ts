export interface LocationSuggestion {
  id: string;
  label: string;
  address: string;
  latitude: number | null;
  longitude: number | null;
  state?: string;
  district?: string;
}

const LOCATION_SEARCH_TIMEOUT_MS = 15_000;

export function buildLocationSearchPath(query: string) {
  return `/api/v1/locations/search?q=${encodeURIComponent(query.trim())}`;
}

export function normalizeLocationSuggestion(value: unknown): LocationSuggestion | null {
  if (!value || typeof value !== 'object') {
    return null;
  }

  const candidate = value as Record<string, unknown>;
  const id = typeof candidate.id === 'string' ? candidate.id.trim() : '';
  const label = typeof candidate.label === 'string' ? candidate.label.trim() : '';
  const address = typeof candidate.address === 'string' ? candidate.address.trim() : '';
  const latitude = candidate.latitude;
  const longitude = candidate.longitude;

  if (
    !label ||
    typeof latitude !== 'number' ||
    !Number.isFinite(latitude) ||
    latitude < -90 ||
    latitude > 90 ||
    typeof longitude !== 'number' ||
    !Number.isFinite(longitude) ||
    longitude < -180 ||
    longitude > 180
  ) {
    return null;
  }

  return {
    id: id || `${latitude}:${longitude}`,
    label,
    address: address || label,
    latitude,
    longitude,
    ...(typeof candidate.state === 'string' && candidate.state.trim()
      ? { state: candidate.state.trim() }
      : {}),
    ...(typeof candidate.district === 'string' && candidate.district.trim()
      ? { district: candidate.district.trim() }
      : {}),
  };
}

/**
 * Calls the guest-safe Malaysia-only location-search route.
 */
export async function searchLocationSuggestions(query: string): Promise<LocationSuggestion[]> {
  const trimmedQuery = query.trim();

  if (trimmedQuery.length < 3) {
    return [];
  }

  const { apiRequest } = await import('./api');
  let response: unknown;
  try {
    response = await apiRequest<unknown>(buildLocationSearchPath(trimmedQuery), {
      auth: false,
      method: 'GET',
      timeoutMs: LOCATION_SEARCH_TIMEOUT_MS,
    });
  } catch {
    const supported = await apiRequest<unknown>('/api/v1/locations/supported', {
      auth: false,
      method: 'GET',
      timeoutMs: LOCATION_SEARCH_TIMEOUT_MS,
    });
    if (!Array.isArray(supported)) throw new Error('Location search returned an invalid response.');
    const needle = trimmedQuery.toLowerCase();
    return supported
      .flatMap((entry) => {
        if (!entry || typeof entry !== 'object') return [];
        const { state, districts } = entry as { state?: unknown; districts?: unknown };
        if (typeof state !== 'string' || !Array.isArray(districts)) return [];
        const stateSuggestion: LocationSuggestion = {
          id: `area:${state}`,
          label: state,
          address: 'State-wide price search',
          latitude: null,
          longitude: null,
          state,
        };
        const districtSuggestions = districts
          .filter((district): district is string => typeof district === 'string')
          .map((district) => ({
            id: `area:${state}:${district}`,
            label: `${district}, ${state}`,
            address: state,
            latitude: null,
            longitude: null,
            state,
            district,
          }));
        return [stateSuggestion, ...districtSuggestions];
      })
      .filter((suggestion) => {
        const label = suggestion.label.toLowerCase();
        const district = suggestion.district?.toLowerCase();
        const state = suggestion.state?.toLowerCase();
        return (
          label.includes(needle) ||
          Boolean(district && needle.includes(district)) ||
          Boolean(!district && state && needle.includes(state))
        );
      })
      .slice(0, 10);
  }

  const rows = Array.isArray(response)
    ? response
    : response && typeof response === 'object' && Array.isArray((response as { results?: unknown }).results)
      ? (response as { results: unknown[] }).results
      : null;

  if (!rows) {
    throw new Error('Location search returned an invalid response.');
  }

  return rows
    .map(normalizeLocationSuggestion)
    .filter((suggestion): suggestion is LocationSuggestion => suggestion !== null);
}
