import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import type { BackendTokenResponse, BackendUser } from '../api/plannerTypes';
import { ApiError, apiRequest, setSessionExpiredHandler } from '../services/api';
import {
  createHousehold,
  listHouseholds,
  selectActiveHouseholdId,
  type Household,
} from '../services/householdApi';
import {
  normalizeAppProfileData,
  type AppProfileData,
} from '../services/appProfile';
import { clearTokens, getStoredTokens, saveTokens } from '../services/tokenStorage';

interface AuthContextValue {
  isAuthenticated: boolean;
  isLoading: boolean;
  profile: AuthProfile;
  profileSaveError: string | null;
  appProfileData: AppProfileData;
  profileLoadError: string | null;
  retryProfile: () => Promise<AppProfileData>;
  households: readonly Household[];
  activeHouseholdId: number | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshSession: () => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  saveAppProfile: (profileData: AppProfileData) => Promise<void>;
  updateProfile: (profile: AuthProfile) => void;
  refreshHouseholds: () => Promise<readonly Household[]>;
  ensureHousehold: (adults: number, children: number) => Promise<Household>;
  user: BackendUser | null;
}

export interface AuthProfile {
  email: string;
  name: string;
}

const AuthContext = createContext<AuthContextValue | null>(null);

async function persistTokenResponse(response: BackendTokenResponse) {
  await saveTokens({
    accessToken: response.access_token,
    refreshToken: response.refresh_token,
  });
}

interface HydratedProfile {
  appProfileData: AppProfileData;
  profile: AuthProfile;
  loadError: string | null;
}

async function fetchProfile(user: BackendUser): Promise<HydratedProfile> {
  let appProfileData: AppProfileData = {};
  let loadError: string | null = null;
  try {
    const response = await apiRequest<{ profile: unknown }>('/api/v1/profile', {
      method: 'GET',
    });
    appProfileData = normalizeAppProfileData(response.profile);
  } catch {
    loadError = 'Your preferences could not be loaded. Please try again.';
  }

  return {
    appProfileData,
    loadError,
    profile: {
      email: user.email,
      name: appProfileData.display_name?.trim() || user.email.split('@')[0] || '',
    },
  };
}

async function persistAppProfile(profileData: AppProfileData) {
  await apiRequest('/api/v1/profile', {
    body: { profile: profileData },
    method: 'PUT',
  });
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isLoading, setIsLoading] = useState(true);
  const [user, setUser] = useState<BackendUser | null>(null);
  const [profile, setProfile] = useState<AuthProfile>({ email: '', name: '' });
  const [profileSaveError, setProfileSaveError] = useState<string | null>(null);
  const [profileLoadError, setProfileLoadError] = useState<string | null>(null);
  const profileLoadErrorRef = useRef<string | null>(null);
  const [appProfileData, setAppProfileData] = useState<AppProfileData>({});
  const [households, setHouseholds] = useState<readonly Household[]>([]);
  const [activeHouseholdId, setActiveHouseholdId] = useState<number | null>(null);
  const profileSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const appProfileDataRef = useRef<AppProfileData>({});
  const sessionVersionRef = useRef(0);

  const replaceAppProfileData = useCallback((nextProfileData: AppProfileData) => {
    appProfileDataRef.current = nextProfileData;
    setAppProfileData(nextProfileData);
  }, []);

  const replaceProfileLoadError = useCallback((error: string | null) => {
    profileLoadErrorRef.current = error;
    setProfileLoadError(error);
  }, []);

  const retryProfile = useCallback(async (): Promise<AppProfileData> => {
    if (!user) throw new Error('Please sign in again.');
    const version = sessionVersionRef.current;
    const hydrated = await fetchProfile(user);
    if (version !== sessionVersionRef.current) throw new Error('Your account changed. Please try again.');
    replaceProfileLoadError(hydrated.loadError);
    if (hydrated.loadError) throw new Error(hydrated.loadError);
    setProfile(hydrated.profile);
    replaceAppProfileData(hydrated.appProfileData);
    return hydrated.appProfileData;
  }, [user, replaceAppProfileData, replaceProfileLoadError]);

  const refreshHouseholds = useCallback(async (): Promise<readonly Household[]> => {
    const version = sessionVersionRef.current;
    const nextHouseholds = await listHouseholds();
    if (version !== sessionVersionRef.current) return [];
    setHouseholds(nextHouseholds);
    setActiveHouseholdId(selectActiveHouseholdId(nextHouseholds));
    return nextHouseholds;
  }, []);

  const ensureHousehold = useCallback(async (adults: number, children: number): Promise<Household> => {
    const existing = households[0];
    if (existing) return existing;
    const version = sessionVersionRef.current;
    const created = await createHousehold({ adults, children });
    if (version !== sessionVersionRef.current) throw new Error('Your account changed. Please try again.');
    setHouseholds([created]);
    setActiveHouseholdId(created.id);
    return created;
  }, [households]);

  const clearSession = useCallback(async () => {
    sessionVersionRef.current += 1;
    if (profileSaveTimer.current) {
      clearTimeout(profileSaveTimer.current);
      profileSaveTimer.current = null;
    }
    setUser(null);
    setProfile({ email: '', name: '' });
    setProfileSaveError(null);
    replaceProfileLoadError(null);
    replaceAppProfileData({});
    setHouseholds([]);
    setActiveHouseholdId(null);
    await clearTokens();
  }, [replaceAppProfileData, replaceProfileLoadError]);

  const refreshSession = async () => {
    const version = sessionVersionRef.current;
    const currentUser = await apiRequest<BackendUser>('/api/v1/auth/me');
    const hydratedProfile = await fetchProfile(currentUser);
    if (version !== sessionVersionRef.current) return;
    setUser(currentUser);
    setProfile(hydratedProfile.profile);
    replaceProfileLoadError(hydratedProfile.loadError);
    replaceAppProfileData(hydratedProfile.appProfileData);
  };

  const loginWithCredentials = async (email: string, password: string) => {
    const version = sessionVersionRef.current;
    const response = await apiRequest<BackendTokenResponse>('/api/v1/auth/login', {
      auth: false,
      body: {
        client_type: 'MOBILE',
        email,
        password,
      },
      errorScope: 'auth',
      method: 'POST',
      timeoutMs: 60_000,
    });
    if (version !== sessionVersionRef.current) throw new Error('Your session changed. Please try again.');
    const nextVersion = ++sessionVersionRef.current;
    if (profileSaveTimer.current) clearTimeout(profileSaveTimer.current);
    await persistTokenResponse(response);
    const hydratedProfile = await fetchProfile(response.user);
    if (nextVersion !== sessionVersionRef.current) throw new Error('Your session changed. Please try again.');
    setHouseholds([]);
    setActiveHouseholdId(null);
    setProfileSaveError(null);
    setUser(response.user);
    setProfile(hydratedProfile.profile);
    replaceProfileLoadError(hydratedProfile.loadError);
    replaceAppProfileData(hydratedProfile.appProfileData);
    await refreshHouseholds();
  };

  useEffect(() => {
    setSessionExpiredHandler(() => {
      void clearSession();
    });

    return () => setSessionExpiredHandler(null);
  }, [clearSession]);

  useEffect(() => {
    let active = true;
    const version = sessionVersionRef.current;

    async function restoreSession() {
      try {
        const tokens = await getStoredTokens();

        if (tokens) {
          try {
            const currentUser = await apiRequest<BackendUser>('/api/v1/auth/me');
            const restoredProfile = await fetchProfile(currentUser);
            if (active && version === sessionVersionRef.current) {
              setUser(currentUser);
              setProfile(restoredProfile.profile);
              replaceProfileLoadError(restoredProfile.loadError);
              replaceAppProfileData(restoredProfile.appProfileData);
              await refreshHouseholds();
            }
            return;
          } catch (error) {
            // Only a genuine 401 (expired/revoked session) clears the stored
            // tokens. A network failure (offline start, tunnel down) must
            // NOT sign the user out - the tokens stay so the next launch
            // can retry, and this session simply runs anonymously.
            if (active && version === sessionVersionRef.current && error instanceof ApiError && error.status === 401) {
              await clearTokens();
            }
          }
        }
      } catch {
        if (active && version === sessionVersionRef.current) {
          await clearTokens();
          setUser(null);
        }
      } finally {
        if (active) {
          setIsLoading(false);
        }
      }
    }

    restoreSession();

    return () => {
      active = false;
    };
  }, [refreshHouseholds, replaceAppProfileData, replaceProfileLoadError]);

  useEffect(() => () => {
    if (profileSaveTimer.current) clearTimeout(profileSaveTimer.current);
  }, []);

  const updateProfile = useCallback((nextProfile: AuthProfile) => {
    if (!user) return;
    if (profileLoadErrorRef.current) {
      setProfileSaveError(profileLoadErrorRef.current);
      void retryProfile().catch(() => {});
      return;
    }

    const nextName = nextProfile.name;
    const nextAppProfileData: AppProfileData = {
      ...appProfileDataRef.current,
      display_name: nextName.trim(),
    };
    setProfile({ email: user.email, name: nextName });
    replaceAppProfileData(nextAppProfileData);
    setProfileSaveError(null);
    if (profileSaveTimer.current) clearTimeout(profileSaveTimer.current);
    const version = sessionVersionRef.current;
    profileSaveTimer.current = setTimeout(() => {
      profileSaveTimer.current = null;
      if (version !== sessionVersionRef.current) return;
      void persistAppProfile(appProfileDataRef.current).catch((error: unknown) => {
        if (version !== sessionVersionRef.current) return;
        setProfileSaveError(
          error instanceof Error ? error.message : 'Your profile could not be saved.',
        );
      });
    }, 800);
  }, [replaceAppProfileData, retryProfile, user]);

  const saveAppProfile = useCallback(async (nextProfileData: AppProfileData) => {
    if (!user) {
      throw new Error('Please sign in before saving personalization.');
    }

    const currentProfileData = profileLoadErrorRef.current
      ? await retryProfile()
      : appProfileDataRef.current;
    const mergedProfileData: AppProfileData = {
      ...currentProfileData,
      ...nextProfileData,
    };
    const version = sessionVersionRef.current;
    await persistAppProfile(mergedProfileData);
    if (version === sessionVersionRef.current) replaceAppProfileData(mergedProfileData);
  }, [replaceAppProfileData, retryProfile, user]);

  const value = useMemo<AuthContextValue>(
    () => ({
      isAuthenticated: Boolean(user),
      isLoading,
      profile,
      profileSaveError,
      appProfileData,
      profileLoadError,
      retryProfile,
      households,
      activeHouseholdId,
      login: async (email, password) => {
        await loginWithCredentials(email, password);
      },
      logout: async () => {
        const tokens = await getStoredTokens();

        try {
          if (tokens?.refreshToken) {
            await apiRequest('/api/v1/auth/logout', {
              auth: false,
              body: { refresh_token: tokens.refreshToken },
              method: 'POST',
            });
          }
        } finally {
          await clearSession();
        }
      },
      refreshSession,
      refreshHouseholds,
      ensureHousehold,
      register: async (name, email, password) => {
        const version = sessionVersionRef.current;
        const response = await apiRequest<BackendTokenResponse>('/api/v1/auth/register', {
          auth: false,
          body: {
            client_type: 'MOBILE',
            email,
            password,
          },
          errorScope: 'auth',
          method: 'POST',
          timeoutMs: 60_000,
        });
        if (version !== sessionVersionRef.current) throw new Error('Your session changed. Please try again.');
        const nextVersion = ++sessionVersionRef.current;
        if (profileSaveTimer.current) clearTimeout(profileSaveTimer.current);
        await persistTokenResponse(response);
        const trimmedName = name.trim();
        const nextAppProfileData: AppProfileData = trimmedName
          ? { display_name: trimmedName }
          : {};
        if (trimmedName) await persistAppProfile(nextAppProfileData);
        if (nextVersion !== sessionVersionRef.current) throw new Error('Your session changed. Please try again.');
        setHouseholds([]);
        setActiveHouseholdId(null);
        setProfileSaveError(null);
        setUser(response.user);
        setProfile({
          email: response.user.email,
          name: trimmedName || response.user.email.split('@')[0] || '',
        });
        replaceAppProfileData(nextAppProfileData);
        replaceProfileLoadError(null);
        await refreshHouseholds();
      },
      saveAppProfile,
      updateProfile,
      user,
    }),
    [activeHouseholdId, appProfileData, ensureHousehold, households, isLoading, profile, profileSaveError, profileLoadError, retryProfile, replaceProfileLoadError, refreshHouseholds, saveAppProfile, updateProfile, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const contextValue = useContext(AuthContext);

  if (!contextValue) {
    throw new Error('useAuth must be used within AuthProvider');
  }

  return contextValue;
}
