import AsyncStorage from '@react-native-async-storage/async-storage';
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

const ACCESS_TOKEN_KEY = 'wisebasket.mobile.accessToken';
const REFRESH_TOKEN_KEY = 'wisebasket.mobile.refreshToken';

export interface StoredTokens {
  accessToken: string;
  refreshToken: string;
}

const tokenStore =
  Platform.OS === 'web'
    ? {
        deleteItemAsync: (key: string) => AsyncStorage.removeItem(key),
        getItemAsync: (key: string) => AsyncStorage.getItem(key),
        setItemAsync: (key: string, value: string) => AsyncStorage.setItem(key, value),
      }
    : SecureStore;

export async function getStoredTokens(): Promise<StoredTokens | null> {
  const [accessToken, refreshToken] = await Promise.all([
    tokenStore.getItemAsync(ACCESS_TOKEN_KEY),
    tokenStore.getItemAsync(REFRESH_TOKEN_KEY),
  ]);

  return accessToken && refreshToken ? { accessToken, refreshToken } : null;
}

export async function saveTokens(tokens: StoredTokens) {
  await Promise.all([
    tokenStore.setItemAsync(ACCESS_TOKEN_KEY, tokens.accessToken),
    tokenStore.setItemAsync(REFRESH_TOKEN_KEY, tokens.refreshToken),
  ]);
}

export async function clearTokens() {
  await Promise.all([
    tokenStore.deleteItemAsync(ACCESS_TOKEN_KEY),
    tokenStore.deleteItemAsync(REFRESH_TOKEN_KEY),
  ]);
}
