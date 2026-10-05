import { useEffect, useState } from 'react';
import type { ImageStyle, TextStyle, ViewStyle } from 'react-native';

export type TemporaryDevUIValue = number | string;
export type TemporaryDevUIValues = Record<string, TemporaryDevUIValue>;

const RESIZE_MODES = ['contain', 'cover', 'stretch', 'center'] as const;
const REQUIRED_KEYS = [
  'screenPaddingTop',
  'logoWidth',
  'welcomeHeadingFontSize',
  'heroImageHeight',
  'priceActionCardPaddingLeft',
  'recentProductImageResizeMode',
  'tipBodyOffsetY',
  'bottomNavPriceCheckLabelFontSize',
] as const;

const POLL_INTERVAL_MS = 250;
const TUNER_URL = __DEV__
  ? process.env.EXPO_PUBLIC_DEV_UI_TUNER_URL?.replace(/\/+$/, '')
  : undefined;
const VALUES_URL = TUNER_URL ? `${TUNER_URL}/__dev-ui/values` : null;

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object');
}

export function parseTemporaryDevUIValues(payload: unknown): TemporaryDevUIValues | null {
  if (!isRecord(payload) || !isRecord(payload.values)) {
    return null;
  }

  const parsed: TemporaryDevUIValues = {};

  for (const [key, value] of Object.entries(payload.values)) {
    if (typeof value === 'number' && Number.isFinite(value)) {
      parsed[key] = value;
      continue;
    }

    if (typeof value === 'string' && key.endsWith('ResizeMode') && RESIZE_MODES.includes(value as typeof RESIZE_MODES[number])) {
      parsed[key] = value;
      continue;
    }

    return null;
  }

  return REQUIRED_KEYS.every((key) => Object.hasOwn(parsed, key)) ? parsed : null;
}

function valuesEqual(left: TemporaryDevUIValues | null, right: TemporaryDevUIValues): boolean {
  if (!left) return false;

  const leftKeys = Object.keys(left);
  const rightKeys = Object.keys(right);

  return leftKeys.length === rightKeys.length && rightKeys.every((key) => left[key] === right[key]);
}

function numberValue(values: TemporaryDevUIValues | null, key: string): number | undefined {
  const value = values?.[key];
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
}

function stringValue(values: TemporaryDevUIValues | null, key: string): string | undefined {
  const value = values?.[key];
  return typeof value === 'string' ? value : undefined;
}

function positionStyle(values: TemporaryDevUIValues | null, prefix: string): ViewStyle {
  const style: ViewStyle = {};
  const offsetX = numberValue(values, `${prefix}OffsetX`);
  const offsetY = numberValue(values, `${prefix}OffsetY`);

  for (const side of ['Top', 'Right', 'Bottom', 'Left'] as const) {
    const margin = numberValue(values, `${prefix}Margin${side}`);
    if (margin !== undefined) style[`margin${side}`] = margin;
  }

  if (offsetX !== undefined && offsetY !== undefined && (offsetX !== 0 || offsetY !== 0)) {
    style.transform = [{ translateX: offsetX ?? 0 }, { translateY: offsetY ?? 0 }];
  }

  return style;
}

export function temporaryBoxStyle(
  values: TemporaryDevUIValues | null,
  prefix: string,
  options: {
    baseTransform?: ViewStyle['transform'];
    heightMode?: 'height' | 'minHeight';
    widthMode?: 'width' | 'minWidth';
    disableFlexWhenWidthSet?: boolean;
  } = {},
): ViewStyle {
  const style: ViewStyle = positionStyle(values, prefix);
  const width = numberValue(values, `${prefix}Width`);
  const height = numberValue(values, `${prefix}Height`);
  const minWidth = numberValue(values, `${prefix}MinWidth`);
  const minHeight = numberValue(values, `${prefix}MinHeight`);
  const heightKey = options.heightMode === 'minHeight' ? 'minHeight' : 'height';
  const widthKey = options.widthMode === 'minWidth' ? 'minWidth' : 'width';

  if (options.baseTransform || style.transform) {
    style.transform = [...(options.baseTransform ?? []), ...(style.transform ?? [])] as ViewStyle['transform'];
  }

  if (width !== undefined && width > 0) style[widthKey] = width;
  if (height !== undefined && height > 0) style[heightKey] = height;
  if (minWidth !== undefined && minWidth > 0) style.minWidth = minWidth;
  if (minHeight !== undefined && minHeight > 0) style.minHeight = minHeight;
  if (options.disableFlexWhenWidthSet && width !== undefined && width > 0) style.flex = 0;

  for (const side of ['Top', 'Right', 'Bottom', 'Left'] as const) {
    const padding = numberValue(values, `${prefix}Padding${side}`);
    if (padding !== undefined) style[`padding${side}`] = padding;
  }

  const radius = numberValue(values, `${prefix}BorderRadius`);
  if (radius !== undefined) style.borderRadius = radius;

  return style;
}

export function temporaryTextStyle(values: TemporaryDevUIValues | null, prefix: string): TextStyle {
  const style: TextStyle = positionStyle(values, prefix);
  const fontSize = numberValue(values, `${prefix}FontSize`);
  const lineHeight = numberValue(values, `${prefix}LineHeight`);
  const letterSpacing = numberValue(values, `${prefix}LetterSpacing`);
  const width = numberValue(values, `${prefix}Width`);
  const height = numberValue(values, `${prefix}Height`);
  const maxWidth = numberValue(values, `${prefix}MaxWidth`);

  if (fontSize !== undefined) style.fontSize = fontSize;
  if (lineHeight !== undefined) style.lineHeight = lineHeight;
  if (letterSpacing !== undefined) style.letterSpacing = letterSpacing;
  if (width !== undefined && width > 0) style.width = width;
  if (height !== undefined && height > 0) style.height = height;
  if (maxWidth !== undefined && maxWidth > 0) style.maxWidth = maxWidth;

  for (const side of ['Top', 'Right', 'Bottom', 'Left'] as const) {
    const padding = numberValue(values, `${prefix}Padding${side}`);
    if (padding !== undefined) style[`padding${side}`] = padding;
  }

  return style;
}

export function temporaryImageStyle(values: TemporaryDevUIValues | null, prefix: string): ImageStyle {
  const style = positionStyle(values, prefix) as ImageStyle;
  const width = numberValue(values, `${prefix}Width`);
  const height = numberValue(values, `${prefix}Height`);
  const radius = numberValue(values, `${prefix}BorderRadius`);

  if (width !== undefined && width > 0) style.width = width;
  if (height !== undefined && height > 0) style.height = height;
  if (radius !== undefined) style.borderRadius = radius;

  return style;
}

export function temporaryIconStyle(values: TemporaryDevUIValues | null, prefix: string): TextStyle {
  return positionStyle(values, prefix);
}

export function temporaryIconSize(values: TemporaryDevUIValues | null, prefix: string, fallback: number): number {
  return numberValue(values, `${prefix}Size`) ?? fallback;
}

export function temporaryResizeMode(values: TemporaryDevUIValues | null, prefix: string, fallback: 'contain' | 'cover' | 'stretch' | 'center') {
  return stringValue(values, `${prefix}ResizeMode`) as 'contain' | 'cover' | 'stretch' | 'center' | undefined ?? fallback;
}

export function temporaryNumber(values: TemporaryDevUIValues | null, key: string, fallback: number): number {
  return numberValue(values, key) ?? fallback;
}

export function useTemporaryDevUIValues(): TemporaryDevUIValues | null {
  const [values, setValues] = useState<TemporaryDevUIValues | null>(null);

  useEffect(() => {
    if (!__DEV__ || !VALUES_URL) {
      return undefined;
    }

    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let controller: AbortController | null = null;

    const poll = async () => {
      controller = new AbortController();

      try {
        const response = await fetch(VALUES_URL, {
          headers: { 'cache-control': 'no-cache' },
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`Dev UI server returned ${response.status}.`);
        }

        const nextValues = parseTemporaryDevUIValues(await response.json());
        if (!nextValues) {
          throw new Error('Dev UI server returned invalid values.');
        }

        if (!stopped) {
          setValues((current) => (valuesEqual(current, nextValues) ? current : nextValues));
        }
      } catch {
        if (!stopped) setValues(null);
      } finally {
        controller = null;
        if (!stopped) timer = setTimeout(poll, POLL_INTERVAL_MS);
      }
    };

    void poll();

    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
      controller?.abort();
    };
  }, []);

  return __DEV__ ? values : null;
}
