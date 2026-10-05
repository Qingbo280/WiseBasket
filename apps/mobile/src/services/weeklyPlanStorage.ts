import AsyncStorage from '@react-native-async-storage/async-storage';
import {
  normalizeWeeklyPlanSnapshot,
  type WeeklyPlanSnapshot,
} from './weeklyPlanSnapshot';

const WEEKLY_PLAN_STORAGE_PREFIX = 'wisebasket.weeklyPlan.v1.';

function weeklyPlanStorageKey(owner: string): string {
  return `${WEEKLY_PLAN_STORAGE_PREFIX}${encodeURIComponent(owner)}`;
}

export async function loadWeeklyPlanSnapshot(owner: string): Promise<WeeklyPlanSnapshot | null> {
  const key = weeklyPlanStorageKey(owner);
  try {
    const stored = await AsyncStorage.getItem(key);
    if (!stored) return null;
    const snapshot = normalizeWeeklyPlanSnapshot(JSON.parse(stored));
    if (!snapshot) await AsyncStorage.removeItem(key);
    return snapshot;
  } catch {
    return null;
  }
}

export async function saveWeeklyPlanSnapshot(
  owner: string,
  snapshot: WeeklyPlanSnapshot,
): Promise<void> {
  await AsyncStorage.setItem(weeklyPlanStorageKey(owner), JSON.stringify(snapshot));
}

export async function clearWeeklyPlanSnapshot(owner: string): Promise<void> {
  await AsyncStorage.removeItem(weeklyPlanStorageKey(owner));
}
