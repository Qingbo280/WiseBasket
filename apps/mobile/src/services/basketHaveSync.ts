/** Last-intent-wins, one-at-a-time Have writes for one active household. */
export interface BasketHaveIntent<T> {
  householdId: number;
  foodIds: readonly string[];
  onApplied: (items: T[]) => void;
  onFailed: (error: unknown, persistedItems?: T[]) => void;
}

/** Reconcile only the failed intent's choices, never a newer edit. Manual
 * pantry rows do not force Need/Skip back to Have: buying more is valid. */
export function reconcileFailedHaveChoices<T extends { productId: string; choice: 'have' | 'need' | 'skip' }>(
  current: readonly T[], intended: readonly T[], previous: readonly T[],
  availableIds: ReadonlySet<string>, managedHaveIds: ReadonlySet<string>,
): T[] {
  const wanted = new Map(intended.map((item) => [item.productId, item.choice]));
  const before = new Map(previous.map((item) => [item.productId, item.choice]));
  return current.map((item) => {
    if (wanted.get(item.productId) !== item.choice) return item;
    if (item.choice === 'have' && !availableIds.has(item.productId)) {
      return { ...item, choice: before.get(item.productId) === 'skip' ? 'skip' : 'need' };
    }
    if (item.choice !== 'have' && managedHaveIds.has(item.productId)) return { ...item, choice: 'have' };
    return item;
  });
}

export class BasketHaveSyncQueue<T> {
  private activeHouseholdId: number | null = null;
  private generation = 0;
  private pending: BasketHaveIntent<T> | null = null;
  private draining: Promise<void> | null = null;

  constructor(
    private readonly replace: (householdId: number, foodIds: readonly string[]) => Promise<T[]>,
    private readonly refresh: (householdId: number) => Promise<T[]>,
  ) {}

  cancelExcept(householdId: number | null) {
    if (this.activeHouseholdId === householdId) return;
    this.activeHouseholdId = householdId;
    this.pending = null;
    this.generation += 1;
  }

  enqueue(intent: BasketHaveIntent<T>) {
    this.cancelExcept(intent.householdId);
    this.pending = {
      ...intent,
      foodIds: [...new Set(intent.foodIds)].sort(),
    };
    if (!this.draining) {
      this.draining = this.drain().finally(() => {
        this.draining = null;
        if (this.pending) this.enqueue(this.pending);
      });
    }
  }

  async whenIdle(): Promise<void> {
    while (this.draining) await this.draining;
  }

  private async drain(): Promise<void> {
    while (this.pending) {
      const intent = this.pending;
      this.pending = null;
      const generation = this.generation;
      let items: T[];
      try {
        items = await this.replace(intent.householdId, intent.foodIds);
      } catch (firstError) {
        // Reconcile uncertain writes with a GET, then retry only the newest
        // desired set once. Permanent failure remains visible to the caller.
        try {
          await this.refresh(intent.householdId);
        } catch {
          // The retry may still succeed after a transient read failure.
        }
        if (generation !== this.generation || this.pending) continue;
        try {
          items = await this.replace(intent.householdId, intent.foodIds);
        } catch (error) {
          let persistedItems: T[] | undefined;
          try { persistedItems = await this.refresh(intent.householdId); } catch { /* Outcome remains unknown. */ }
          if (generation === this.generation && !this.pending) intent.onFailed(error ?? firstError, persistedItems);
          continue;
        }
      }
      if (generation === this.generation && !this.pending) intent.onApplied(items);
    }
  }
}
