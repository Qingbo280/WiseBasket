import type { BackendTokenResponse } from '../api/plannerTypes';
import { fetch as expoFetch } from 'expo/fetch';
import { clearTokens, getStoredTokens, saveTokens } from './tokenStorage';

const API_BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL?.replace(/\/+$/, '');
const REQUEST_TIMEOUT_MS = 30000;

type ApiMethod = 'DELETE' | 'GET' | 'PATCH' | 'POST' | 'PUT';

interface ApiRequestOptions {
  auth?: boolean;
  body?: unknown;
  errorScope?: 'auth' | 'plan' | 'request';
  method?: ApiMethod;
  retryOnUnauthorized?: boolean;
  /** Per-request timeout override (plan requests need ~90 s for LLM work). */
  timeoutMs?: number;
}

let sessionExpiredHandler: (() => void) | null = null;

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export function setSessionExpiredHandler(handler: (() => void) | null) {
  sessionExpiredHandler = handler;
}

function getApiBaseUrl() {
  if (!API_BASE_URL) {
    throw new ApiError('API URL is not configured. Set EXPO_PUBLIC_API_BASE_URL.', 0);
  }

  return API_BASE_URL;
}

function formatDetail(detail: unknown) {
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (item && typeof item === 'object' && 'msg' in item) {
          return String(item.msg);
        }

        return String(item);
      })
      .join(', ');
  }

  return typeof detail === 'string' ? detail : null;
}

function userSafeMessage(status: number, body: any, scope: ApiRequestOptions['errorScope'] = 'request') {
  const detail = formatDetail(body?.detail ?? body?.message);

  if (detail) {
    return detail;
  }
  if (status === 401) {
    return 'Please sign in again.';
  }
  if (status === 403) {
    return 'You do not have permission to do this.';
  }
  if (status === 422) {
    return scope === 'plan'
      ? 'Some planning details need to be corrected.'
      : 'Some details need to be corrected.';
  }
  if (status >= 500) {
    if (scope === 'auth') {
      return 'WiseBasket could not complete authentication right now. Please try again.';
    }
    if (scope === 'plan') {
      return 'WiseBasket could not generate a plan right now. Please try again.';
    }
    return 'WiseBasket could not complete the request right now. Please try again.';
  }

  return `Request failed with status ${status}.`;
}

async function parseBody(response: Response) {
  const text = await response.text();

  if (!text) {
    return null;
  }

  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

// The backend ROTATES the refresh token on every /auth/refresh (the old one
// is revoked immediately). Concurrent 401s must therefore share a single
// in-flight refresh - otherwise the second caller replays the just-revoked
// token, the refresh fails and the user is silently signed out.
let refreshPromise: Promise<boolean> | null = null;

async function refreshAccessToken(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = doRefreshAccessToken().finally(() => {
      refreshPromise = null;
    });
  }

  return refreshPromise;
}

async function doRefreshAccessToken() {
  const tokens = await getStoredTokens();

  if (!tokens?.refreshToken) {
    return false;
  }

  const response = await expoFetch(`${getApiBaseUrl()}/api/v1/auth/refresh`, {
    body: JSON.stringify({ refresh_token: tokens.refreshToken }),
    headers: { 'content-type': 'application/json' },
    method: 'POST',
  });
  const body = await parseBody(response);

  if (!response.ok) {
    await clearTokens();
    sessionExpiredHandler?.();
    return false;
  }

  const tokenBody = body as BackendTokenResponse;
  await saveTokens({
    accessToken: tokenBody.access_token,
    refreshToken: tokenBody.refresh_token,
  });
  return true;
}

export async function apiRequest<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const { auth = true, body, method = body === undefined ? 'GET' : 'POST' } = options;
  const tokens = auth ? await getStoredTokens() : null;
  const isMultipart = typeof FormData !== 'undefined' && body instanceof FormData;
  const headers: Record<string, string> = {
    accept: 'application/json',
  };

  if (body !== undefined && !isMultipart) {
    headers['content-type'] = 'application/json';
  }
  if (auth && tokens?.accessToken) {
    headers.authorization = `Bearer ${tokens.accessToken}`;
  }

  let response: Response;

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), options.timeoutMs ?? REQUEST_TIMEOUT_MS);

  try {
    response = await expoFetch(`${getApiBaseUrl()}${path}`, {
      body: body === undefined ? undefined : isMultipart ? body : JSON.stringify(body),
      headers,
      method,
      signal: controller.signal,
    });
  } catch (err) {
    // React Native does not consistently surface AbortController cancellation
    // as a DOM-style AbortError, so also inspect the signal itself.
    if (controller.signal.aborted || (err instanceof Error && err.name === 'AbortError')) {
      throw new ApiError(`Request timed out for ${getApiBaseUrl()}. Please try again.`, 0);
    }

    throw new ApiError(`Connection failed for ${getApiBaseUrl()}. Check your API URL and network.`, 0);
  } finally {
    clearTimeout(timeout);
  }

  const parsedBody = await parseBody(response);

  if (response.status === 401 && auth && options.retryOnUnauthorized !== false) {
    const refreshed = await refreshAccessToken();

    if (refreshed) {
      return apiRequest<T>(path, { ...options, retryOnUnauthorized: false });
    }
  }

  if (!response.ok) {
    throw new ApiError(userSafeMessage(response.status, parsedBody, options.errorScope), response.status);
  }

  return parsedBody as T;
}
