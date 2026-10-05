export type LocationSource = 'gps' | 'manual';

export interface ConfirmedLocation {
  address: string;
  shortLabel?: string;
  latitude?: number;
  longitude?: number;
  source: LocationSource;
  state?: string;
  district?: string;
  confirmedAt: string;
}

export type LocationCandidate = Omit<ConfirmedLocation, 'confirmedAt'>;

export function getLocationDisplayLabel(
  location: Pick<ConfirmedLocation, 'address' | 'shortLabel'>,
): string {
  return location.shortLabel?.trim() || location.address.trim() || 'Set your shopping location';
}

export function createConfirmedLocation(
  candidate: LocationCandidate,
  confirmedAt = new Date().toISOString(),
): ConfirmedLocation {
  return {
    ...candidate,
    address: candidate.address.trim() || getLocationDisplayLabel(candidate),
    confirmedAt,
  };
}

function optionalTrimmedString(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value.trim() : undefined;
}

function optionalCoordinate(value: unknown, minimum: number, maximum: number): number | undefined {
  return typeof value === 'number'
    && Number.isFinite(value)
    && value >= minimum
    && value <= maximum
    ? value
    : undefined;
}

export function normalizeStoredConfirmedLocation(value: unknown): ConfirmedLocation | null {
  if (!value || typeof value !== 'object') return null;

  const candidate = value as Record<string, unknown>;
  const address = optionalTrimmedString(candidate.address);
  const confirmedAt = optionalTrimmedString(candidate.confirmedAt);
  const source = candidate.source === 'gps' || candidate.source === 'manual'
    ? candidate.source
    : null;
  if (!address || !confirmedAt || !source) return null;

  const shortLabel = optionalTrimmedString(candidate.shortLabel);
  const latitude = optionalCoordinate(candidate.latitude, -90, 90);
  const longitude = optionalCoordinate(candidate.longitude, -180, 180);
  const state = optionalTrimmedString(candidate.state);
  const district = optionalTrimmedString(candidate.district);

  return {
    address,
    confirmedAt,
    source,
    ...(shortLabel ? { shortLabel } : {}),
    ...(latitude !== undefined ? { latitude } : {}),
    ...(longitude !== undefined ? { longitude } : {}),
    ...(state ? { state } : {}),
    ...(district ? { district } : {}),
  };
}
