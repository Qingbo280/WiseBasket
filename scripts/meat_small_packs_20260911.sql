-- 2026-09-11 basket-realism data fix: register small retail portions for fresh
-- meat / seafood / eggs alongside the existing 1 kg bulk rows.
--
-- WHY: PriceCatcher observes meat and seafood in 1 kg packs only, so the
-- planner's whole-pack model made fresh meat structurally unbuyable for small
-- or budget-tight households (a 1 kg beef pack breaches the per-item share cap
-- for 1A, and even for 2A2C it eats the H5 protein budget and evicts the
-- calcium anchor - CP-SAT proved OPTIMAL Calcium-33% with beef locked). In
-- Malaysian wet markets meat and fish are routinely cut to order (~250 g), and
-- eggs are sold in 10-egg trays. With the multi-pack code path (select_pack /
-- the habit-pick retry's smallest-pack lock) these rows give small households
-- realistic options without touching large-household bulk pricing.
--
-- Scope: fresh meat + seafood + eggs ONLY. Dry protein goods (beans, lentils,
-- peanuts, dried squid) and milk keep their existing packs - they are stocked
-- in fixed retail packs, not cut to order.
--
-- Unit price note: the per-food representative price stays derived from the
-- 1 kg observations; RM/100g is size-independent, so small portions price
-- linearly. The nightly daily_pricecatcher_update.py never writes
-- PURCHASE_MASS rows (verified 2026-09-11), so these rows are stable.
--
-- Idempotent: safe to re-run (guarded by the NOT EXISTS check).
-- Rollback: delete the rows tagged in evidence_note:
--   delete from unit_conversion
--    where conversion_type='PURCHASE_MASS'
--      and evidence_note like '%SMALL_PACK_2026-09-11%';

-- 250 g wet-market portion for fresh meat & seafood.
insert into unit_conversion
    (canonical_food_id, conversion_type, source_unit, target_unit,
     factor, production_eligible, evidence_note)
select cf.canonical_food_id, 'PURCHASE_MASS', '250 g', 'g',
       250.00000000, true,
       'SMALL_PACK_2026-09-11: 250 g wet-market portion registered so small / '
       'budget-tight households get a buyable fresh-meat option (PriceCatcher '
       'observes 1 kg only; per-100g price implied by the existing 1 kg '
       'representative price). Registered by planner basket-realism revision '
       '2026-09-11.'
from canonical_food cf
where cf.canonical_food_id in (
        -- red meat & poultry
        'SF001','SF002','SF003','SF004','SF005','SF006',
        'SF008','SF009','SF010','SF011',
        'SF013','SF014','SF015','SF016','SF017','SF201',
        -- seafood
        'SF022','SF023','SF024','SF025','SF026','SF027','SF028','SF029',
        'SF030','SF032','SF033','SF034','SF035','SF036','SF037','SF038',
        'SF039','SF040','SF041','SF042','SF043','SF044','SF045','SF046',
        'SF047','SF048','SF049','SF050'
      )
  and not exists (
      select 1 from unit_conversion uc
      where uc.canonical_food_id = cf.canonical_food_id
        and uc.conversion_type = 'PURCHASE_MASS'
        and uc.factor = 250.00000000
        and uc.production_eligible
  );

-- 10-egg tray (~58 g/egg) as the small egg pack.
insert into unit_conversion
    (canonical_food_id, conversion_type, source_unit, target_unit,
     factor, production_eligible, evidence_note)
select 'SF018', 'PURCHASE_MASS', '10 biji', 'g',
       580.00000000, true,
       'SMALL_PACK_2026-09-11: 10-egg tray registered so the habit-pick retry '
       'can lock a household''s egg pick at a small portion (30-egg tray '
       'eats the H5 protein budget and evicts the calcium anchor in '
       'multi-pick personas; CP-SAT proved OPTIMAL Calcium-33%). Registered '
       'by planner basket-realism revision 2026-09-11.'
where not exists (
    select 1 from unit_conversion
    where canonical_food_id = 'SF018'
      and conversion_type = 'PURCHASE_MASS'
      and factor = 580.00000000
      and production_eligible
);
