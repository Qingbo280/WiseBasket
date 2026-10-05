-- SF091 lai fruit: "1 biji" was 1000 g (parser default) -> 180 g per piece.
-- Identity curated as pear (USDA FDC 167776 Bartlett, medium pear ~180 g,
-- same policy as red apple item 1486). Fixes bogus RM0.20/100g basket filler.
BEGIN;

UPDATE unit_conversion
SET factor = 180.00000000,
    evidence_note = 'Piece-weight policy 180 g/pc (item 31): LAI KUNING (SAIZ M) curated as pear (USDA FDC 167776 Bartlett); medium pear ~180 g, same policy as red apple item 1486. Fix 2026-09-13: previous 1000 g/pc was a parser default that made lai a bogus RM0.20/100g basket filler.'
WHERE canonical_food_id = 'SF091'
  AND conversion_type = 'PURCHASE_MASS'
  AND source_unit = '1 biji';

UPDATE food_price_observation
SET price_rm_per_100g_purchase = ROUND(price_rm / 1.8, 4),
    price_rm_per_100g_edible   = ROUND(price_rm / 1.8 / COALESCE(edible_yield_fraction, 1.0), 4)
WHERE canonical_food_id = 'SF091';

SELECT refresh_food_price_monthly_agg(m)
FROM (SELECT DISTINCT month FROM food_price_monthly_agg WHERE canonical_food_id='SF091') AS t(m);

COMMIT;

-- verification
SELECT uc.factor, uc.evidence_note FROM unit_conversion uc
WHERE uc.canonical_food_id='SF091' AND uc.conversion_type='PURCHASE_MASS';
SELECT count(*), min(price_rm_per_100g_purchase), max(price_rm_per_100g_purchase)
FROM food_price_observation WHERE canonical_food_id='SF091';
