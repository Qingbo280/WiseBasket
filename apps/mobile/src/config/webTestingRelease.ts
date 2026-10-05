// Web testing / UAT only. Update this version before each release push.
// Keep the same version for UAT and PROD builds of the same release.
export const WEB_APP_VERSION = '3.4.10';

const configuredEnvironment = process.env.EXPO_PUBLIC_APP_ENV?.trim().toUpperCase();
const apiUrl = process.env.EXPO_PUBLIC_API_BASE_URL?.replace(/\/+$/, '');

export const WEB_APP_ENVIRONMENT =
  configuredEnvironment === 'UAT' || configuredEnvironment === 'PROD'
    ? configuredEnvironment
    : !configuredEnvironment && apiUrl === 'https://wisebasket-uat-api.up.railway.app'
      ? 'UAT'
      : 'LOCAL';
