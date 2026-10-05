-- 2026-09-11 basket-realism data fix: register a 2 kg retail pack for white rice
-- (SF110) alongside the existing 10 kg bulk row.
--
-- WHY: PriceCatcher only ever observes rice in 10 kg packs (price-control item),
-- so the planner's single-pack model made rice structurally unbuyable for small
-- households (10 kg breaches both the per-item share cap and the 35% energy-share
-- guard), pushing the solver to flour/sugar as the cheapest small-pack calories
-- (reviewed RM100/2A basket: 2 kg flour, no rice). With the multi-pack code path
-- (select_pack), registering 2 kg gives small households a realistic rice option
-- while large households still get 10 kg bulk.
--
-- Unit price note: the per-food representative price is derived from 10 kg
-- observations; ~RM2.6-2.9/kg for a 2 kg pack is a plausible retail premium.
-- The nightly daily_pricecatcher_update.py never writes PURCHASE_MASS rows
-- (verified 2026-09-11: it only reads EDIBLE_YIELD), so this row is stable.
--
-- Idempotent: safe to re-run (guarded by the NOT EXISTS check).
-- Rollback: delete the row tagged in evidence_note:
--   delete from unit_conversion
--    where canonical_food_id='SF110' and conversion_type='PURCHASE_MASS'
--      and evidence_note like '%RICE_SMALL_PACK_2026-09-11%';

insert into unit_conversion
    (canonical_food_id, conversion_type, source_unit, target_unit,
     factor, production_eligible, evidence_note)
select 'SF110', 'PURCHASE_MASS', '2 kg', 'g',
       2000.00000000, true,
       'RICE_SMALL_PACK_2026-0911: 2 kg retail pack registered so small '
       'households get a buyable rice option (PriceCatcher observes 10 kg '
       'only; per-kg price implied by the existing 10 kg representative '
       'price). Registered by planner basket-realism revision 2026-09-11.'
where not exists (
    select 1 from unit_conversion
    where canonical_food_id = 'SF110'
      and conversion_type = 'PURCHASE_MASS'
      and factor = 2000.00000000
      and production_eligible
);
