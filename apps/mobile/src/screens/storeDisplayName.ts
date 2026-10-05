/** Presentation-only store naming. Keep the API/database name untouched. */
export interface StoreDisplayName {
  displayName: string;
  branch: string | null;
}

interface BrandRule {
  pattern: RegExp;
  label: string;
}

// Longer aliases must come first so "AEON MAXVALU" is not reduced to "AEON".
const BRAND_RULES: readonly BrandRule[] = [
  { pattern: /^(?:PASARAYA\s+)?AEON\s+MAXVALU\s+THE\s+PRIME\b/i, label: 'AEON MaxValu The Prime' },
  { pattern: /^(?:PASARAYA\s+)?AEON\s+MAXVALU\s+PRIME\b/i, label: 'AEON MaxValu Prime' },
  { pattern: /^(?:PASARAYA\s+)?AEON\s+MAXVALU\b/i, label: 'AEON MaxValu' },
  { pattern: /^(?:PASARAYA\s+)?GIANT\s+HYPERMARKET\b/i, label: 'Giant' },
  { pattern: /^(?:PASARAYA\s+)?GIANT\s+SUPERMARKET\b/i, label: 'Giant' },
  { pattern: /^(?:PASARAYA\s+)?GIANT\s+MINI\b/i, label: 'Giant Mini' },
  { pattern: /^(?:PASARAYA\s+)?SEGI\s+CASH\s*(?:&|AND)\s*CARRY\b/i, label: 'Segi Cash & Carry' },
  { pattern: /^(?:PASARAYA\s+)?BEN['’]?S\s+INDEPENDENT\s+GROCER\b/i, label: "Ben's Independent Grocer" },
  { pattern: /^(?:PASARAYA\s+)?VILLAGE\s+GROCER\b/i, label: 'Village Grocer' },
  { pattern: /^(?:PASARAYA\s+)?JAYA\s+GROCER\b/i, label: 'Jaya Grocer' },
  { pattern: /^(?:PASARAYA\s+)?HERO\s+MARKET\b/i, label: 'Hero Market' },
  { pattern: /^(?:PASARAYA\s+)?HERO\s+MART\b/i, label: 'Hero Mart' },
  { pattern: /^(?:PASARAYA\s+)?99\s*SPEED\s*MART\b/i, label: '99 Speedmart' },
  { pattern: /^(?:PASAR\s+MINI\s+)?99\s*SPEEDMART\b/i, label: '99 Speedmart' },
  { pattern: /^PASARAYA\s+MINI\s+ECONSAVE\b/i, label: 'Econsave' },
  { pattern: /^(?:PASARAYA\s+)?ECONSAVE\s+MART\b/i, label: 'Econsave Mart' },
  { pattern: /^(?:PASARAYA\s+)?ECONSAVE\s+EXPRESS\b/i, label: 'Econsave Express' },
  { pattern: /^(?:PASARAYA\s+)?ECONSAVE(?:\s+CASH\s*(?:&|AND)\s*CARRY)?\b/i, label: 'Econsave' },
  { pattern: /^(?:PASARAYA\s+)?CHECKERS(?:\s+CASH\s*(?:&|AND)\s*CARRY)?\b/i, label: 'Checkers' },
  { pattern: /^(?:PASARAYA\s+)?LOTUS['’]?S?(?:\s+STORES?)?\b/i, label: "Lotus's" },
  { pattern: /^(?:PASARAYA\s+)?AEON\s+BIG\b/i, label: 'AEON Big' },
  { pattern: /^(?:PASARAYA\s+)?AEON\s+SUPERMARKET\b/i, label: 'AEON Supermarket' },
  { pattern: /^(?:PASARAYA\s+)?AEON\b/i, label: 'AEON' },
  { pattern: /^(?:PASARAYA\s+)?SEGI\s+FRESH\b/i, label: 'Segi Fresh' },
  { pattern: /^(?:PASARAYA\s+)?NSK\s+GROCER\b/i, label: 'NSK Grocer' },
  { pattern: /^(?:PASARAYA\s+)?NSK\s+TRADE\b/i, label: 'NSK Trade' },
  { pattern: /^(?:PASARAYA\s+)?GIANT\b/i, label: 'Giant' },
  { pattern: /^(?:PASARAYA\s+)?MERCATO\b/i, label: 'Mercato' },
  { pattern: /^(?:PASARAYA\s+)?THE\s+STORE\b/i, label: 'The Store' },
  { pattern: /^(?:PASARAYA\s+)?TMG\s+MART\b/i, label: 'TMG Mart' },
  { pattern: /^(?:PASARAYA\s+)?TMG\s+EXPRESS\b/i, label: 'TMG Express' },
  { pattern: /^(?:PASARAYA\s+)?TMC\b/i, label: 'TMC' },
  { pattern: /^PASARAYA\s+WELL\b/i, label: 'Pasaraya Well' },
];

const CORPORATE_SUFFIX = /(?:\s*,?\s*(?:SDN\.?\s*BHD\.?|BERHAD|BHD\.?|SDN\.?))+\s*$/i;
const TRAILING_STORE_TYPE = /\s+(?:SUPERMARKET|HYPERMARKET|CASH\s*(?:&|AND)\s*CARRY|GROCERIES|GROCER|STORES?)\s*$/i;

function cleanName(value: string): string {
  return value
    .replace(/[\u00a0\t\r\n]+/g, ' ')
    .replace(/\s+/g, ' ')
    .replace(/\s+([,)])/g, '$1')
    .replace(/([(])\s+/g, '$1')
    .replace(/[.]+$/g, '')
    .trim();
}

function titleCase(value: string): string {
  return cleanName(value)
    .toLowerCase()
    .replace(/\b(ttdi|kl|bbcc|lsh\d+)\b/gi, (token) => token.toUpperCase())
    .replace(/\b(tmn|taman)\b/gi, 'Taman')
    .replace(/\b(jln|jalan)\b/gi, 'Jalan')
    .replace(/\b(sek|seksyon|seksyen)\b/gi, 'Seksyen')
    .replace(/\b[a-z]/g, (letter) => letter.toUpperCase());
}

function stripNoise(value: string): string {
  return cleanName(value)
    .replace(CORPORATE_SUFFIX, '')
    .replace(TRAILING_STORE_TYPE, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function splitKnownBrand(value: string): StoreDisplayName | null {
  // Do not strip words such as "Grocer" before brand matching; they are part
  // of brands like Village Grocer and Ben's Independent Grocer.
  const candidate = cleanName(value).replace(CORPORATE_SUFFIX, '').trim();
  for (const rule of BRAND_RULES) {
    const match = candidate.match(rule.pattern);
    if (!match) continue;
    const remainder = stripNoise(candidate.slice(match[0].length))
      .replace(/^[\s,\-–—|:]+/, '')
      .replace(/[\s,\-–—|:]+$/, '');
    return {
      displayName: rule.label,
      branch: remainder ? titleCase(remainder) : null,
    };
  }
  return null;
}

/**
 * Produces compact brand/branch labels for cards while preserving the raw name
 * for API requests, accessibility labels, and full-detail views.
 */
export function getStoreDisplayName(name: string): StoreDisplayName {
  const raw = cleanName(name || '');
  if (!raw) return { displayName: 'Store', branch: null };

  // Parentheses are the most reliable branch delimiter in the current data.
  const parenthesized = raw.match(/^(.+?)\s*\(\s*([^()]*)\s*\)\s*$/);
  if (parenthesized) {
    const known = splitKnownBrand(parenthesized[1]);
    return {
      displayName: known?.displayName ?? titleCase(stripNoise(parenthesized[1])),
      branch: titleCase(parenthesized[2]) || known?.branch || null,
    };
  }

  const known = splitKnownBrand(raw);
  if (known) return known;

  // Support names supplied as "brand - branch" or "brand, branch".
  const separated = raw.match(/^(.+?)(?:\s+(?:-|–|—|\|)\s+|,\s+)(.+)$/);
  if (separated) {
    const knownPrefix = splitKnownBrand(separated[1]);
    if (knownPrefix) {
      return { displayName: knownPrefix.displayName, branch: titleCase(separated[2]) };
    }
  }

  // Unknown future stores stay readable and never produce an empty label.
  return { displayName: titleCase(stripNoise(raw)) || titleCase(raw), branch: null };
}
