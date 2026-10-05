import { apiRequest } from './api';

export interface Household {
  id: number;
  name: string | null;
  adults: number;
  children: number;
}

export interface CreateHouseholdInput {
  name?: string;
  adults: number;
  children: number;
}

export async function listHouseholds(): Promise<Household[]> {
  return apiRequest<Household[]>('/api/v1/households', { method: 'GET' });
}

export async function createHousehold(input: CreateHouseholdInput): Promise<Household> {
  return apiRequest<Household>('/api/v1/households', {
    body: input,
    method: 'POST',
  });
}

export async function updateHousehold(
  householdId: number,
  input: CreateHouseholdInput,
): Promise<Household> {
  return apiRequest<Household>(`/api/v1/households/${householdId}`, {
    body: input,
    method: 'PATCH',
  });
}

export function selectActiveHouseholdId(households: readonly Household[]): number | null {
  return households[0]?.id ?? null;
}
