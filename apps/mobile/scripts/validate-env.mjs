import fs from 'node:fs';
import path from 'node:path';

const mode = process.argv.includes('--public') ? 'public' : 'local-phone';
const appRoot = path.resolve(import.meta.dirname, '..');
const envFiles = ['.env.local', '.env'].map((name) => path.join(appRoot, name));

function parseEnvFile(filePath) {
  if (!fs.existsSync(filePath)) {
    return {};
  }

  const out = {};
  const text = fs.readFileSync(filePath, 'utf8');
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#')) {
      continue;
    }

    const index = line.indexOf('=');
    if (index === -1) {
      continue;
    }

    const key = line.slice(0, index).trim();
    const value = line.slice(index + 1).trim().replace(/^['"]|['"]$/g, '');
    out[key] = value;
  }
  return out;
}

const fileEnv = Object.assign({}, ...envFiles.map(parseEnvFile));
const apiBaseUrl = (process.env.EXPO_PUBLIC_API_BASE_URL || fileEnv.EXPO_PUBLIC_API_BASE_URL || '').trim();
const assetBaseUrl = (process.env.EXPO_PUBLIC_ASSET_BASE_URL || fileEnv.EXPO_PUBLIC_ASSET_BASE_URL || '').trim();

function fail(message) {
  console.error(`Mobile environment check failed: ${message}`);
  process.exit(1);
}

if (!apiBaseUrl) {
  fail('EXPO_PUBLIC_API_BASE_URL is required.');
}

let parsedUrl;
try {
  parsedUrl = new URL(apiBaseUrl);
} catch {
  fail('EXPO_PUBLIC_API_BASE_URL must be a valid URL.');
}

if (!['http:', 'https:'].includes(parsedUrl.protocol)) {
  fail('EXPO_PUBLIC_API_BASE_URL must use http or https.');
}

if (apiBaseUrl.endsWith('/')) {
  fail('EXPO_PUBLIC_API_BASE_URL should not end with a trailing slash.');
}
let parsedAssetUrl = null;
if (assetBaseUrl) {
  try {
    parsedAssetUrl = new URL(assetBaseUrl);
  } catch {
    fail('EXPO_PUBLIC_ASSET_BASE_URL must be a valid URL when set.');
  }

  if (!['http:', 'https:'].includes(parsedAssetUrl.protocol)) {
    fail('EXPO_PUBLIC_ASSET_BASE_URL must use http or https when set.');
  }

  if (assetBaseUrl.endsWith('/')) {
    fail('EXPO_PUBLIC_ASSET_BASE_URL should not end with a trailing slash.');
  }
}
if (mode === 'public') {
  if (!parsedAssetUrl) {
    fail('EXPO_PUBLIC_ASSET_BASE_URL is required for public builds.');
  }

  if (parsedUrl.protocol !== 'https:') {
    fail('public builds must use an HTTPS backend URL.');
  }
  if (
    ['localhost', '127.0.0.1'].includes(parsedUrl.hostname) ||
    /^192\.168\./.test(parsedUrl.hostname) ||
    /^10\./.test(parsedUrl.hostname)
  ) {
    fail('public builds must not point to localhost, emulator, or private LAN addresses.');
  }

  if (parsedAssetUrl?.protocol === 'http:') {
    fail('public builds must use an HTTPS asset URL.');
  }
}

console.log(`Mobile environment check passed for ${mode}: ${parsedUrl.origin}`);
