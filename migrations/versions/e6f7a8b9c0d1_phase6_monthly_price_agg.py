"""Phase 6: food_price_monthly_agg + refresh function

Capacity tiering for the service layer (UAT/Prod): food x state x district x
month median edible-100g price, refreshed monthly by the daily PriceCatcher
updater (scripts/daily_pricecatcher_update.py calls
refresh_food_monthly_agg(current_month) when the table exists).

Design (DATA_COMPLETION_PLAN.md / DATA_MIGRATION_MASTER_PLAN.md Phase 6):
  (canonical_food_id, district, state, month, median_rm_per_100g_edible,
   obs_count, source_mix) ~= 128-201 foods x ~150 districts x months.

The upgrade also backfills all existing months so the table is useful
immediately; refresh is delete-and-rebuild per month, idempotent.

Revision: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
"""
from alembic import op

revision = "e6f7a8b9c0d1"
down_revision = "d5e6f7a8b9c0"


def upgrade() -> None:
    op.execute(
        """
        create table food_price_monthly_agg (
            canonical_food_id            varchar not null
                 references canonical_food(canonical_food_id),
            state                        text   not null,
            district                     text   not null,
            month                        char(7) not null,
            median_rm_per_100g_edible    numeric(10,4) not null,
            obs_count                    integer not null,
            source_mix                   text   not null,
            primary key (canonical_food_id, state, district, month)
        )
        """
    )
    op.execute(
        """
        create or replace function refresh_food_price_monthly_agg(p_month text)
        returns void language sql as $$
            delete from food_price_monthly_agg where month = p_month;
            insert into food_price_monthly_agg
            select f.canonical_food_id,
                   l.state,
                   coalesce(l.district, ''),
                   to_char(f.observed_date, 'YYYY-MM'),
                   percentile_cont(0.5) within group
                       (order by f.price_rm_per_100g_edible)::numeric(10,4),
                   count(*)::int,
                   string_agg(distinct f.source_dataset_version, '+'
                              order by f.source_dataset_version)
            from food_price_observation f
            join location l on l.location_id = f.location_id
            where f.quality_status = 'PASS'
              and f.canonical_food_id is not null
              and f.price_rm_per_100g_edible is not null
              and to_char(f.observed_date, 'YYYY-MM') = p_month
            group by 1, 2, 3, 4
        $$;
        """
    )
    # One-time backfill of every month present in the observation table.
    op.execute(
        """
        insert into food_price_monthly_agg
        select f.canonical_food_id,
               l.state,
               coalesce(l.district, ''),
               to_char(f.observed_date, 'YYYY-MM'),
               percentile_cont(0.5) within group
                   (order by f.price_rm_per_100g_edible)::numeric(10,4),
               count(*)::int,
               string_agg(distinct f.source_dataset_version, '+'
                          order by f.source_dataset_version)
        from food_price_observation f
        join location l on l.location_id = f.location_id
        where f.quality_status = 'PASS'
          and f.canonical_food_id is not null
          and f.price_rm_per_100g_edible is not null
        group by 1, 2, 3, 4
        on conflict do nothing
        """
    )


def downgrade() -> None:
    op.execute("drop function if exists refresh_food_price_monthly_agg(text)")
    op.execute("drop table if exists food_price_monthly_agg")
