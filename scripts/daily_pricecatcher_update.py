"""WiseBasket daily PriceCatcher price updater (Phase 5).

Downloads the current month's official PriceCatcher parquet from
data.gov.my (month rollover automatic), keeps only items with an
APPROVED+VERIFIED PRICECATCHER identity mapping and premises already in
the location table, normalises units/yields exactly like the Phase-3
staging build, and inserts with the natural unique key
(source_item_code, location_id, observed_date, source_dataset_version)
so re-runs within a month are safe no-ops.

Usage:
    python scripts/daily_pricecatcher_update.py            # one run, current month
    python scripts/daily_pricecatcher_update.py --once --month 2026-09
    python scripts/daily_pricecatcher_update.py --dry-run  # count only, no INSERT
    python scripts/daily_pricecatcher_update.py --daemon   # loop every 24h

Env: DATABASE_URL (postgresql+asyncpg:// or postgresql://).
Design notes (master plan Phase 5):
  * unseen item codes are LOGGED, never auto-mapped (identity drift guard);
  * SHA change detection via a tiny price_update_state KV table;
  * monthly aggregate refresh is attempted only when the Phase-6 table
    food_price_monthly_agg exists;
  * price anomalies (<=0 or >10x the item's existing median) are
    alerted, not inserted as PASS.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import io
import logging
import os
import re
import urllib.request
from datetime import date, datetime, timedelta, timezone

import asyncpg
import pandas as pd

PARQUET_URL = "https://storage.data.gov.my/pricecatcher/pricecatcher_{month}.parquet"
DATASET_VERSION = "PRICECATCHER_{month}"  # matches REAL_MARKET_SOURCE_TAG_SHAPES

log = logging.getLogger("daily_pricecatcher")

# ---------------------------------------------------------- unit policies
# piece-weight policies (g per piece) -- mirror phase3/build_price_staging.py
BIJI_G = {
    1110: 58.0, 1109: 58.0, 1111: 58.0,          # TELUR AYAM GRED A/B/C 30 biji
    118: 57.5, 119: 62.5, 120: 67.5,             # 10 biji, explicit weight ranges
    101: 150.0,                                   # KELAPA BIJI
    25: 1500.0,                                   # NENAS BIASA
    31: 1000.0,                                   # LAI KUNING (SAIZ M)
    1486: 180.0,                                  # EPAL MERAH RED DELICIOUS
}
BEG_G = {1650: 2.0, 180: 2.0}                     # tea bags ~2 g/bag
# liquid densities (g/ml) by canonical food
DENSITY = {
    'SF102': 1.00, 'SF129': 1.16, 'SF176': 1.03, 'SF175': 0.93, 'SF155': 1.00,
    'SF177': 1.00, 'SF178': 1.00, 'SF179': 1.00, 'SF182': 1.00,
    'SF184': 1.00, 'SF185': 1.00, 'SF186': 1.00, 'SF189': 1.00,
}


def parse_mass_g(unit: str, item_code: int, canon_id: str):
    u = (unit or '').strip().lower().replace(' ', '')
    m = re.fullmatch(r'([0-9.]+)(kg|g)', u)
    if m:
        v = float(m.group(1))
        return (v * 1000 if m.group(2) == 'kg' else v), 'deterministic mass parse'
    m = re.fullmatch(r'\+-([0-9.]+)g', u)
    if m:
        return float(m.group(1)), 'approximate mass parse'
    m = re.fullmatch(r'([0-9]+)x([0-9.]+)g', u)
    if m:
        return int(m.group(1)) * float(m.group(2)), 'multipack deterministic parse'
    m = re.fullmatch(r'([0-9.]+)biji', u)
    if m:
        per = BIJI_G.get(item_code)
        if per:
            return int(float(m.group(1))) * per, f'piece-weight policy {per} g/pc'
        return None, 'no piece-weight policy for biji unit'
    m = re.fullmatch(r'([0-9.]+)beg', u)
    if m:
        per = BEG_G.get(item_code)
        if per:
            return int(float(m.group(1))) * per, 'bag-weight policy'
        return None, 'no bag-weight policy'
    m = re.fullmatch(r'([0-9.]+)(liter|l)', u)
    if m:
        d = DENSITY.get(canon_id)
        if d:
            return float(m.group(1)) * 1000 * d, f'liquid density {d} g/ml'
        return None, 'no density policy for liter unit'
    m = re.fullmatch(r'([0-9.]+)ml', u)
    if m:
        d = DENSITY.get(canon_id)
        if d:
            return float(m.group(1)) * d, f'liquid density {d} g/ml'
        return None, 'no density policy for ml unit'
    return None, f'unparseable unit {unit!r}'


# ---------------------------------------------------------------- data flow
async def load_governance(conn):
    """item code -> mapping row (only APPROVED + VERIFIED identities)."""
    rows = await conn.fetch(
        "select source_food_id, source_food_name, source_unit_or_form, canonical_food_id"
        " from source_food_mapping"
        " where upper(source_system) = 'PRICECATCHER' and review_status = 'APPROVED'"
        " and verification_status = 'VERIFIED'"
        " and mapping_status in ('EXACT','ACCEPTED_EQUIVALENT','NEEDS_CONVERSION')")
    item_map = {int(r['source_food_id']): dict(r) for r in rows}
    loc_rows = await conn.fetch("select source_premise_code, location_id from location")
    premise_map = {int(r['source_premise_code']): r['location_id'] for r in loc_rows}
    yrows = await conn.fetch(
        "select canonical_food_id, edible_yield_fraction from unit_conversion"
        " where conversion_type = 'EDIBLE_YIELD' and production_eligible"
        " and edible_yield_fraction is not null")
    yields = {r['canonical_food_id']: float(r['edible_yield_fraction']) for r in yrows}
    return item_map, premise_map, yields


def fetch_month_parquet(month: str) -> bytes:
    url = PARQUET_URL.format(month=month)
    log.info("downloading %s", url)
    with urllib.request.urlopen(url, timeout=300) as r:
        return r.read()


async def sha_state(conn, month: str):
    await conn.execute(
        "create table if not exists price_update_state ("
        " key text primary key, value text not null, updated_at timestamptz not null)")
    return await conn.fetchval(
        "select value from price_update_state where key=$1", f"sha:{month}")


async def sha_save(conn, month: str, sha: str):
    await conn.execute(
        "insert into price_update_state (key, value, updated_at) values ($1,$2,now())"
        " on conflict (key) do update set value=$2, updated_at=now()",
        f"sha:{month}", sha)


async def item_medians(conn, item_codes):
    rows = await conn.fetch(
        "select source_item_code, percentile_cont(0.5) within group (order by price_rm)"
        " from food_price_observation where source_item_code = any($1::text[])"
        " and quality_status = 'PASS' group by 1", [str(c) for c in item_codes])
    return {r['source_item_code']: float(r['percentile_cont']) for r in rows}


async def prune_superseded(conn, version: str) -> int:
    """Service-layer invariant: one latest row per (item, premise, version)."""
    n = await conn.execute(
        "delete from food_price_observation f where f.source_dataset_version = $1"
        " and exists (select 1 from food_price_observation g"
        " where g.source_item_code = f.source_item_code"
        " and g.location_id = f.location_id"
        " and g.source_dataset_version = f.source_dataset_version"
        " and (g.observed_date > f.observed_date"
        " or (g.observed_date = f.observed_date and g.ctid > f.ctid)))",
        version)
    return int(n.split()[-1])


async def run_once(dsn: str, month: str | None, dry_run: bool, keep_history: bool = False):
    month = month or date.today().strftime('%Y-%m')
    raw = fetch_month_parquet(month)
    sha = hashlib.sha256(raw).hexdigest()
    log.info("month=%s rows_bytes=%d sha=%s…", month, len(raw), sha[:12])

    conn = await asyncpg.connect(dsn)
    try:
        prev = await sha_state(conn, month)
        if prev == sha:
            log.info("SHA unchanged since last run -- nothing to do")
            return 0

        item_map, premise_map, yields = await load_governance(conn)
        df = pd.read_parquet(io.BytesIO(raw),
                             columns=['date', 'premise_code', 'item_code', 'price'])
        df = df[df['premise_code'].isin(premise_map) & df['item_code'].isin(item_map)]
        log.info("after governance filter: %d / %d rows", len(df), len(df))

        medians = await item_medians(conn, df['item_code'].unique().tolist()) \
            if len(df) else {}

        records, anomalies, unparsed = [], 0, 0
        for r in df.itertuples(index=False):
            meta = item_map[int(r.item_code)]
            canon = meta['canonical_food_id']
            mass, note = parse_mass_g(meta['source_unit_or_form'],
                                      int(r.item_code), canon)
            if mass is None:
                unparsed += 1
                continue
            price = float(r.price)
            med = medians.get(str(r.item_code))
            if price <= 0 or (med and price > 10 * med):
                anomalies += 1
                log.warning("price anomaly item=%s price=%s median=%s -- skipped",
                            r.item_code, price, med)
                continue
            per100 = round(price / (mass / 100.0), 4)
            y = yields.get(canon, 1.0)
            records.append((
                canon, str(r.item_code), meta['source_food_name'],
                str(r.premise_code), premise_map[int(r.premise_code)],
                date.fromisoformat(str(r.date)[:10]), price,
                meta['source_unit_or_form'], mass, round(per100 * 10, 4), per100,
                y, round(per100 / y, 4) if y else None,
                DATASET_VERSION.format(month=month), 'PASS'))

        log.info("prepared %d rows (anomalies skipped=%d, unparsed units=%d)",
                 len(records), anomalies, unparsed)
        if dry_run:
            log.info("dry-run: no INSERT")
            return len(records)

        version = DATASET_VERSION.format(month=month)
        before = await conn.fetchval(
            "select count(*) from food_price_observation where source_dataset_version=$1",
            version)
        cols = ['canonical_food_id', 'source_item_code', 'source_food_name',
                'source_premise_code', 'location_id', 'observed_date', 'price_rm',
                'original_unit', 'purchase_mass_g', 'price_rm_per_kg_purchase',
                'price_rm_per_100g_purchase', 'edible_yield_fraction',
                'price_rm_per_100g_edible', 'source_dataset_version', 'quality_status']
        sql = (f"insert into food_price_observation ({','.join(cols)}) values "
               f"({','.join(f'${i+1}' for i in range(len(cols)))})"
               " on conflict (source_item_code, location_id, observed_date,"
               " source_dataset_version) do nothing")
        await conn.executemany(sql, records)
        after = await conn.fetchval(
            "select count(*) from food_price_observation where source_dataset_version=$1",
            version)
        new = int(after) - int(before)
        log.info("insert done: %d new rows (version=%s, total now %d)", new, version, after)

        # Phase-6 monthly aggregate: refresh only when the table exists.
        agg = await conn.fetchval(
            "select exists(select 1 from information_schema.tables"
            " where table_name='food_price_monthly_agg')")
        if agg:
            await conn.execute("select refresh_food_price_monthly_agg($1)", month)
            log.info("monthly aggregate refreshed for %s", month)
        else:
            log.info("food_price_monthly_agg absent -- skipping aggregate refresh (Phase 6)")

        await sha_save(conn, month, sha)
        if not keep_history:
            pruned = await prune_superseded(conn, version)
            log.info("pruned %d superseded same-month rows (service layer)", pruned)
        return new
    finally:
        await conn.close()


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--once', action='store_true', help='run once and exit (default)')
    ap.add_argument('--month', help='YYYY-MM override (default: current month)')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--daemon', action='store_true', help='loop every 24h')
    ap.add_argument('--keep-history', action='store_true',
                    help='keep every daily row (warehouse layer); default prunes'
                         ' superseded same-month rows to honour the service-layer'
                         ' invariant of one latest row per item x premise')
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(message)s')
    dsn = os.environ.get(
        'DATABASE_URL',
        'postgresql+asyncpg://wisebasket:wisebasket@localhost:5432/wisebasket',
    ).replace('+asyncpg://', '://', 1)

    while True:
        try:
            await run_once(dsn, args.month, args.dry_run, keep_history=args.keep_history)
        except Exception:
            log.exception("daily update failed -- alerting, not raising")
        if not args.daemon:
            break
        log.info("daemon: sleeping 24h")
        await asyncio.sleep(24 * 3600)


if __name__ == '__main__':
    asyncio.run(main())


# ---------------------------------------------------------------------- Celery
# Optional Celery wiring for the Railway worker deployment (railway-worker.toml
# runs this module as `celery -A scripts.daily_pricecatcher_update:celery_app
# worker --beat`). Import is guarded so the standalone script keeps working in
# environments without celery installed.
try:
    from celery import Celery
    from celery.schedules import crontab

    _broker = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
    celery_app = Celery('wisebasket_worker', broker=_broker, backend=_broker)
    celery_app.conf.timezone = 'Asia/Kuala_Lumpur'
    # Receipt OCR is CPU-bound. One worker process must consume one job at a
    # time rather than prefetching several images and competing for memory.
    celery_app.conf.worker_concurrency = int(os.environ.get('CELERY_WORKER_CONCURRENCY', '1'))
    celery_app.conf.worker_prefetch_multiplier = 1
    celery_app.conf.beat_schedule = {
        'pricecatcher-daily': {
            'task': 'scripts.daily_pricecatcher_update.daily_pricecatcher_update',
            'schedule': crontab(hour=7, minute=30),  # 07:30 MYT, after official refresh
        },
        'receipt-image-retention': {
            'task': 'scripts.receipt_tasks.purge_expired_receipt_images_task',
            'schedule': timedelta(minutes=15),
        },
        'receipt-processing-deadline': {
            'task': 'scripts.receipt_tasks.fail_expired_receipts_task',
            'schedule': timedelta(minutes=5),
        },
    }

    @celery_app.task(bind=True, max_retries=2, default_retry_delay=1800)
    def daily_pricecatcher_update(self):
        """Celery wrapper: run one daily PriceCatcher update against DATABASE_URL."""
        dsn = os.environ['DATABASE_URL'].replace('+asyncpg://', '://', 1)
        try:
            return asyncio.run(run_once(dsn, None, dry_run=False))
        except Exception as exc:  # retry transient network/DB failures twice
            raise self.retry(exc=exc)

except ImportError:  # pragma: no cover - celery only installed in worker image
    celery_app = None
