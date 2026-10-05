import type { AuthTokenResponse } from '../api/plannerTypes';
import { apiRequest } from './api';
import { clearTokens, saveTokens } from './tokenStorage';

const AUTH_TIMEOUT_MS = 15_000;

export interface AccountCredentials {
  email: string;
  password: string;
}

export interface AccountRegistration extends AccountCredentials {
  name: string;
}

export interface AccountProfile {
  email: string;
  name: string;
}

interface ProfileBlob {
  display_name?: string;
}

async function fetchProfileBlob(): Promise<ProfileBlob | null> {
  const response = await apiRequest<{ profile: ProfileBlob | null }>('/api/v1/profile', {
    method: 'GET',
  });
  return response.profile ?? null;
}

async function persistDisplayName(name: string) {
  await apiRequest('/api/v1/profile', {
    body: { profile: { display_name: name } },
    method: 'PUT',
  });
}

/** Register a new account against the real backend, persist the issued
 *  tokens, and store the display name in the per-account profile blob so
 *  every device sees the same profile after login. */
export async function registerAccount(details: AccountRegistration): Promise<AccountProfile> {
  const tokens = await apiRequest<AuthTokenResponse>('/api/v1/auth/register', {
    auth: false,
    body: {
      client_type: 'MOBILE',
      email: details.email,
      password: details.password,
    },
    errorScope: 'auth',
    timeoutMs: AUTH_TIMEOUT_MS,
  });
  await saveTokens({
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token,
  });

  const name = details.name.trim();
  if (name) {
    await persistDisplayName(name);
  }

  return { email: tokens.user.email, name };
}

/** Log in against the real backend and hydrate the display name from the
 *  per-account profile blob (falls back to the email local part). */
export async function loginAccount(credentials: AccountCredentials): Promise<AccountProfile> {
  const tokens = await apiRequest<AuthTokenResponse>('/api/v1/auth/login', {
    auth: false,
    body: {
      client_type: 'MOBILE',
      email: credentials.email,
      password: credentials.password,
    },
    errorScope: 'auth',
    timeoutMs: AUTH_TIMEOUT_MS,
  });
  await saveTokens({
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token,
  });

  let name = '';
  try {
    name = (await fetchProfileBlob())?.display_name?.trim() ?? '';
  } catch {
    // A profile blob is optional; never block login on it.
  }

  if (!name) {
    name = tokens.user.email.split('@')[0] ?? '';
  }

  return { email: tokens.user.email, name };
}

/** Persist an edited display name into the per-account profile blob. */
export async function saveAccountDisplayName(name: string) {
  await persistDisplayName(name.trim());
}

export async function logoutAccount() {
  await clearTokens();
}
