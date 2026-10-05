"""catalogue expansion v2: FULL_DETAIL + PARTIAL_DETAIL foods (idempotent revision)

Revision ID: f19b6d84c3a7
Revises: e7a2c9f04b18
Create Date: 2026-09-06 00:00:00.000000

REVISED BEFORE FIRST SUCCESSFUL DEPLOY -- same revision id, new content.
The original batch of 20 draft foods (SF073-SF092) was found, before this
migration ever applied cleanly anywhere, to overlap the already-deployed i2
data pack: 8 of the 20 (margarine, lime, fine salt, milk powder, grape,
watermelon, honeydew, dragon fruit) already exist in the authoritative
catalogue as SF061/SF055/SF056/SF062/SF052/SF047/SF049/SF050, each already
carrying the same bilingual identity, the same PriceCatcher item mapping,
and a purchase-mass conversion. Inserting them again would violate the
global unique constraints on food_alias(alias_name, language, source_system)
and source_food_mapping(source_system, source_dataset_version,
source_food_id), and would duplicate live identities -- so the original
upgrade() could never run on any database that already holds the pack, and
on a bare database it would create semantic duplicates. Team direction:
overlapping identities must not be admitted twice.

This revision therefore does three things, all idempotent (existence-dedup
on every insert, safe to re-run, safe on any database state):

1. NEW_FOODS -- the 12 genuinely-new foods (SF073-SF076, SF079, SF080,
   SF083-SF088), inserted only if their canonical id does not already exist.
   Every food has a verified English + Malaysian Malay name and a real
   PriceCatcher price mapping (August 2026 national panel). Nutrition is
   MyFCD 1997 wherever available; round eggplant and shallot use a justified
   USDA FoodData Central fallback because no matching MyFCD record exists.
   Verified MyFCD 'Gram Edible Portion' yields (2026-09-06 campaign) make
   cucumber, broccoli, galangal, green chili, calamansi lime, grated
   coconut, tamarind, bird's eye chili and brown sugar FULL_DETAIL; bell
   pepper, eggplant, shallot and brown sugar remain PARTIAL_DETAIL where
   their own evidence review could not support a field (brown sugar's
   approximate pooled-brand '+-500g' unit stays unconverted under the same
   range-to-quantum policy already on record for SF002's egg grades).

2. MERGE_EVIDENCE -- for the 8 overlapping concepts, ONLY the incremental
   evidence is merged into the existing canonical food, and only what the
   existing food demonstrably lacks (dedup by source identity, not by row):
   an extra PriceCatcher item mapping where the pack mapped only a sibling
   item (margarine 206 'MARJERIN PLANTA'; watermelon 21 seedless), the
   MyFCD source-identity mapping (none of the 8 had one -- their nutrition
   is USDA-based), and an evidenced EDIBLE_YIELD row where none exists.
   No canonical_food row, no alias, and no nutrition row is touched: the
   existing foods' USDA-current nutrition stays authoritative (demoting it
   to swap in the MyFCD record is a separate, deliberate data decision).
   Merge targets are verified fail-closed against their known English
   identity before anything is written.

3. YIELD_BACKFILLS -- the verified MyFCD edible-portion campaign values
   (2026-09-06, myfcd_yields_20260906.json evidence trail) for pre-existing
   pack foods that lack an EDIBLE_YIELD conversion row, plus explicitly
   labelled POLICY_DEFAULT proposals where the MyFCD article is
   unreachable; nothing is fabricated beyond that artifact.

The 8 draft ids SF077/SF078/SF081/SF082/SF089/SF090/SF091/SF092 are retired
in data/canonical_food_identity_ledger.csv (SF063 precedent) so they can
never be silently reallocated.

NOTE: this migration deliberately does NOT load food_price_observation
rows -- no migration in this repository's history ever has; real price
time-series data has always been loaded out-of-band.
"""
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f19b6d84c3a7"
down_revision: Union[str, Sequence[str], None] = "e7a2c9f04b18"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

REVIEWER_EMAIL = "admin@wisebasket.com"
REVIEWED_AT = datetime(2026, 9, 6, tzinfo=timezone.utc)

# Each entry:
#   sf_id, english_name, malay_name, category,
#   aliases: [(name, lang, source_system)]  -- beyond the base EN/MS pair
#   pricecatcher: [(item_code, item_name, unit, mapping_status, evidence)]
#   myfcd: (dataset_version, record_id, source_name, nutrients-dict, evidence)
#   purchase_mass: (source_unit, factor_g) or None
#   yield_: (fraction, evidence_note) or None
NEW_FOODS = [
    dict(
        sf_id="SF073", english_name="cucumber", malay_name="Timun", category="vegetables",
        aliases=[],
        pricecatcher=[("113", "TIMUN", "1kg", "EXACT",
                       "Official PriceCatcher item 113 'TIMUN', category SAYUR-SAYURAN, unit 1kg. "
                       "26,822 real observations, 1,619 shops, 16/16 states, August 2026 panel.")],
        myfcd=("MYFCD_1997", "105031", "Cucumber (Timun) ; Cucumis sativus",
               dict(energy_kcal=16, protein_g=0.5, fat_g=0.0, carbohydrate_g=3.4, fibre_g=0.6,
                    vitamin_c_mg=9.7),
               "MyFCD 1997 Food ID 105031, re-verified directly against the live record."),
        purchase_mass=("1kg", 1000),
        yield_=(0.71, "MyFCD 105031 'Gram Edible Portion: 71g', re-verified directly (2026-09-06 campaign)."),
    ),
    dict(
        sf_id="SF074", english_name="broccoli", malay_name="Brokoli", category="vegetables",
        aliases=[],
        pricecatcher=[("1479", "BROKOLI", "1kg", "EXACT",
                       "Official PriceCatcher item 1479 'BROKOLI', unit 1kg. 3,010 real observations, "
                       "914 shops, 16/16 states, August 2026 panel.")],
        myfcd=("MYFCD_1997", "105012", "Broccoli (Brokoli) ; Brassica oleracea",
               dict(energy_kcal=29, protein_g=4.1, fat_g=0.1, carbohydrate_g=2.8, fibre_g=1.0,
                    vitamin_c_mg=85.0),
               "MyFCD 1997 Food ID 105012, re-verified directly against the live record."),
        purchase_mass=("1kg", 1000),
        yield_=(1.00, "MyFCD 105012 'Gram Edible Portion: 100g' (zero refuse), re-verified directly."),
    ),
    dict(
        sf_id="SF075", english_name="galangal", malay_name="Lengkuas", category="vegetables",
        aliases=[],
        pricecatcher=[("1819", "LENGKUAS", "1kg", "EXACT",
                       "Official PriceCatcher item 1819 'LENGKUAS', unit 1kg. 24,572 real observations, "
                       "1,471 shops, 16/16 states, August 2026 panel.")],
        myfcd=("MYFCD_1997", "114029", "Galangal (Lengkuas) ; Languas galanga",
               dict(energy_kcal=36, protein_g=0.9, fat_g=0.7, carbohydrate_g=6.5, fibre_g=1.6),
               "MyFCD 1997 Food ID 114029, re-verified directly against the live record."),
        purchase_mass=("1kg", 1000),
        yield_=(0.72, "MyFCD 114029 'Gram Edible Portion: 72g', re-verified directly."),
    ),
    dict(
        sf_id="SF076", english_name="green chili", malay_name="Cili Hijau", category="vegetables",
        aliases=[("Lada Hijau", "ms", "MYFCD")],
        pricecatcher=[("92", "CILI HIJAU", "1kg", "EXACT",
                       "Official PriceCatcher item 92 'CILI HIJAU', unit 1kg. 21,157 real observations, "
                       "1,288 shops, 15/16 states, August 2026 panel. Species confirmed Capsicum annuum "
                       "via MyFCD cross-reference. Naming decision: KPDN/PriceCatcher's 'Cili Hijau' is "
                       "used as the canonical ms-MY display name (this project's default rule: prefer "
                       "the retail/PriceCatcher term); MyFCD's own 'Lada Hijau' is preserved as an alias, "
                       "not discarded -- both are genuine Malaysian-government sources for the same "
                       "species/record.")],
        myfcd=("MYFCD_1997", "105024", "Chilli, green (Lada hijau) ; Capsicum annuum",
               dict(energy_kcal=40, protein_g=2.1, fat_g=0.5, carbohydrate_g=6.8, fibre_g=3.0,
                    vitamin_c_mg=158.0),
               "MyFCD 1997 Food ID 105024, filed under 'Lada hijau' -- see naming-decision note above."),
        purchase_mass=("1kg", 1000),
        yield_=(0.95, "MyFCD 105024 'Gram Edible Portion: 95g', re-verified directly."),
    ),
    dict(
        sf_id="SF079", english_name="green bell pepper", malay_name="Lada Benggala Hijau",
        category="vegetables",
        aliases=[],
        pricecatcher=[("1128", "LADA BENGGALA HIJAU (CAPSICUM)", "1kg", "EXACT",
                       "Official PriceCatcher item 1128, unit 1kg. 4,056 real observations, 1,180 "
                       "shops, 16/16 states, August 2026 panel.")],
        myfcd=("MYFCD_CURRENT", "R105022", "CAPSICUM, GREEN (LADA BENGALA, HIJAU)",
               dict(energy_kcal=20.33, protein_g=0.68, fat_g=0.15, carbohydrate_g=3.4, fibre_g=1.3),
               "MyFCD 'current' module (Institute for Medical Research Malaysia, published 2024-12-03), "
               "food code R105022. MyFCD spells it 'Bengala' (single g); PriceCatcher/candidate spec use "
               "'Benggala' (double g) -- same food, recorded here as 'Lada Benggala Hijau' per the "
               "PriceCatcher/retail convention."),
        purchase_mass=("1kg", 1000),
        yield_=None,  # PARTIAL_DETAIL: record shows only a per-piece serving weight, not refuse%
    ),
    dict(
        sf_id="SF080", english_name="calamansi lime", malay_name="Limau Kesturi", category="fruit",
        aliases=[("Limau Kasturi", "ms", "WISEBASKET_CURATED")],
        pricecatcher=[("1928", "LIMAU KASTURI", "1kg", "EXACT",
                       "Official PriceCatcher item 1928 'LIMAU KASTURI', unit 1kg. 25,046 real "
                       "observations, 1,503 shops, 16/16 states, August 2026 panel. PriceCatcher's own "
                       "retail spelling is 'Kasturi'; the DBP/MyFCD-verified dictionary spelling is "
                       "'Kesturi' -- 'Limau Kesturi' is used as canonical, 'Limau Kasturi' preserved as "
                       "an alias since it is the real, common retail label.")],
        myfcd=("MYFCD_1997", "106046", "Lime, musk (Limau kesturi) ; Citrus microcarpa",
               dict(energy_kcal=25, protein_g=0.4, fat_g=0.3, carbohydrate_g=5.1, fibre_g=0.1,
                    vitamin_c_mg=41.6),
               "MyFCD 1997 Food ID 106046; spelling independently corroborated by DBP PRPM."),
        purchase_mass=("1kg", 1000),
        yield_=(0.54, "MyFCD 106046 'Gram Edible Portion: 54g', re-verified via the live .tmp endpoint "
                      "(2026-09-06 campaign)."),
    ),
    dict(
        sf_id="SF083", english_name="round eggplant", malay_name="Terung Bulat", category="vegetables",
        aliases=[],
        pricecatcher=[("1923", "TERUNG BULAT", "1kg", "EXACT",
                       "Official PriceCatcher item 1923 'TERUNG BULAT', unit 1kg. 2,980 real "
                       "observations, 856 shops, 15/16 states, August 2026 panel.")],
        myfcd=("USDA_FDC_2019", "169228", "Eggplant, raw (SR Legacy)",
               dict(energy_kcal=25, protein_g=0.98, fat_g=0.18, carbohydrate_g=5.88, fibre_g=3.0),
               "MyFCD has no 'terung'/eggplant/brinjal/aubergine record (checked both the 1997 and "
               "'current' modules -- zero hits). USDA FoodData Central SR Legacy FDC ID 169228, species "
               "Solanum melongena confirmed, generic globe/American eggplant -- MODERATE identity match "
               "(species matches; not a Malaysian-cultivar-specific record). Justified fallback per this "
               "project's evidence hierarchy: Malaysian evidence genuinely unavailable."),
        purchase_mass=("1kg", 1000),
        yield_=None,  # PARTIAL_DETAIL: no edible-portion evidence found
    ),
    dict(
        sf_id="SF084", english_name="shallot", malay_name="Bawang Kecil Merah", category="vegetables",
        aliases=[("Bawang Merah", "ms", "DBP")],
        pricecatcher=[
            ("131", "BAWANG KECIL MERAH ROSE IMPORT (INDIA)", "1kg", "ACCEPTED_EQUIVALENT",
             "Official PriceCatcher item 131, unit 1kg. 18,094 observations, 1,209 shops. Primary "
             "coverage-based representative of the generic 'shallot' concept."),
            ("1442", "BAWANG KECIL MERAH BIASA IMPORT (INDIA)", "1kg", "ACCEPTED_EQUIVALENT",
             "Official PriceCatcher item 1442, unit 1kg. 15,781 observations, 1,010 shops. Same generic "
             "shallot concept, different import grade."),
            ("132", "BAWANG KECIL MERAH IMPORT (THAILAND)", "1kg", "ACCEPTED_EQUIVALENT",
             "Official PriceCatcher item 132, unit 1kg. 5,329 observations, 387 shops. Same generic "
             "shallot concept, different import origin."),
        ],
        myfcd=("USDA_FDC_2019", "170499", "Shallots, raw (SR Legacy)",
               dict(carbohydrate_g=16.8),
               "MyFCD has no shallot/'bawang kecil'/Allium ascalonicum record (checked both modules -- "
               "zero hits; only large onion and pickled-shallot-fritter records exist). USDA FoodData "
               "Central SR Legacy FDC ID 170499 -- carbohydrate value independently re-pulled directly "
               "from the primary API and confirmed. Other macros (energy/protein/fat) for this record "
               "were only found via secondary aggregators during research and were NOT independently "
               "re-verified against the primary API before this migration -- recorded as NULL here "
               "rather than stated as fact; only the one directly-confirmed value is recorded."),
        purchase_mass=("1kg", 1000),
        yield_=None,  # PARTIAL_DETAIL: no edible-portion evidence directly confirmed
    ),
    dict(
        sf_id="SF085", english_name="grated coconut", malay_name="Kelapa Parut", category="other",
        aliases=[],
        pricecatcher=[("102", "KELAPA PARUT", "1kg", "EXACT",
                       "Official PriceCatcher item 102 'KELAPA PARUT', unit 1kg. 834 real observations, "
                       "230 shops, 15/16 states, August 2026 panel. Correctly distinct from coconut "
                       "milk (SF060, an extracted liquid).")],
        myfcd=("MYFCD_1997", "104009", "Coconut flesh, old (Isi kelapa tua)",
               dict(energy_kcal=357, protein_g=6.8, fat_g=34.5, carbohydrate_g=4.7, fibre_g=4.6),
               "MyFCD has no record literally titled 'kelapa parut'/grated coconut (checked -- zero "
               "hits). MyFCD 1997 Food ID 104009 'Coconut flesh, old' is the closest proxy -- grating is "
               "a purely mechanical step that should not materially change composition, but the record "
               "is not itself labeled 'grated' -- MODERATE identity match, not STRONG."),
        purchase_mass=("1kg", 1000),
        yield_=(0.70, "MyFCD 'Coconut (kelapa), old' Food ID 104007 'Gram Edible Portion: 70g', "
                      "live-verified directly (2026-09-06 campaign; supersedes the draft's 104009 "
                      "citation, which is the nutrition proxy record, not the GEP record)."),
    ),
    dict(
        sf_id="SF086", english_name="seedless tamarind", malay_name="Asam Jawa (Tidak Berbiji)",
        category="other",
        aliases=[],
        pricecatcher=[("1604", "ASAM JAWA (TIDAK BERBIJI) ADABI", "200 g", "ACCEPTED_EQUIVALENT",
                       "Official PriceCatcher item 1604, unit 200g. 2,410 real observations, 704 shops, "
                       "16/16 states, August 2026 panel. Deliberately excludes item 1489 'ASAM JAWA "
                       "(BERBIJI)' (WITH seeds), a scientifically distinct product form not evaluated "
                       "here.")],
        myfcd=("MYFCD_1997", "106091", "Tamarind, fresh pods (Buah Asam Jawa) ; Tamarindus indica",
               dict(energy_kcal=313, protein_g=3.5, fat_g=1.0, carbohydrate_g=72.6, fibre_g=1.4),
               "MyFCD has no record for dried/packaged/seedless tamarind pulp specifically. MyFCD 1997 "
               "Food ID 106091 'fresh pods' is the closest available record -- MODERATE identity match "
               "(fresh-pod harvest form vs. dried/packaged/seedless retail form is a real form "
               "mismatch). MyFCD's other tamarind record (114038, 'paste') was rejected: its sodium "
               "value (4,231mg/100g) is implausible for plain tamarind, suggesting a seasoned "
               "preparation, not a suitable nutrition proxy."),
        purchase_mass=("200 g", 200),
        yield_=(0.70, "MyFCD 106091 'Gram Edible Portion: 70g', re-verified via the live .tmp endpoint "
                      "(2026-09-06 campaign)."),
    ),
    dict(
        sf_id="SF087", english_name="bird's eye chili", malay_name="Cili Padi", category="vegetables",
        aliases=[("Cili Api", "ms", "PRICECATCHER")],
        pricecatcher=[("716", "CILI API/PADI HIJAU", "1kg", "EXACT",
                       "Official PriceCatcher item 716 'CILI API/PADI HIJAU', unit 1kg. 1,196 real "
                       "observations, 413 shops, 13/16 states, August 2026 panel. A different species "
                       "(Capsicum frutescens) from the large green chili already in the catalogue "
                       "(SF076, Capsicum annuum) -- genuinely distinct food, not a variant/duplicate. "
                       "KPDN's own item name uses both 'Cili Api' and 'Cili Padi' together; 'Cili Padi' "
                       "is used as canonical (MyFCD's own term), 'Cili Api' preserved as an alias.")],
        myfcd=("MYFCD_1997", "105026", "Chilli, small (Cili padi)",
               dict(energy_kcal=50, protein_g=4.1, fat_g=0.7, carbohydrate_g=6.6, fibre_g=7.4),
               "MyFCD 1997 Food ID 105026. Species (Capsicum frutescens) confirmed via independent "
               "corroborating source (GlobinMed), not MyFCD itself, which does not state a binomial."),
        purchase_mass=("1kg", 1000),
        yield_=(0.94, "MyFCD 105026 'Edible Portion: 94g', found directly on the nutrition record."),
    ),
    dict(
        sf_id="SF088", english_name="brown sugar", malay_name="Gula Merah", category="other",
        aliases=[],
        pricecatcher=[("1588", "GULA MERAH LEMBUT (PELBAGAI JENAMA)", "+- 500g", "CANDIDATE",
                       "Official PriceCatcher item 1588, official unit recorded as an APPROXIMATE "
                       "'+- 500g' across multiple pooled brands ('PELBAGAI JENAMA'). 1,525 real "
                       "observations, 451 shops, 16/16 states confirm real market presence, but -- "
                       "same reasoning already on record for fine salt (retired draft SF081) and "
                       "SF002's egg-grade weights -- this project declines to convert an approximate/"
                       "pooled-brand weight into a single deterministic purchase-mass value without a "
                       "ratified range-to-quantum policy. Mapping status CANDIDATE, not EXACT; no "
                       "purchase_mass/price observations loaded this round.")],
        myfcd=("MYFCD_1997", "107017", "Sugar, brown (Gula merah)",
               dict(energy_kcal=353, protein_g=1.3, fat_g=0.2, carbohydrate_g=86.6, fibre_g=0.0),
               "MyFCD 1997 Food ID 107017. Generic 'brown sugar' entry; does not specify soft-paste "
               "('lembut') vs. hardened-block form -- MODERATE identity match, not STRONG."),
        purchase_mass=None,  # PARTIAL_DETAIL: approximate/pooled-brand unit, not converted
        yield_=(1.00, "MyFCD 107017 'Gram Edible Portion: 100g' (zero refuse), re-verified via the "
                      "live .tmp endpoint (2026-09-06 campaign)."),
        skip_price_observations=True,
    ),
]

# Overlapping-identity merges: the V2 draft proposed these 8 as NEW canonical
# foods (SF077/078/081/082/089/090/091/092), but each concept already exists
# in the deployed i2 pack under the target id below -- verified by direct
# database inspection (same bilingual identity, same PriceCatcher item
# already mapped, purchase mass already present). Only the incremental
# evidence is merged, and only what the target demonstrably lacks. Those 8
# draft ids are retired in the identity ledger and are never created here.
#
# Each entry:
#   target, expected_names: fail-closed identity guard (case-insensitive)
#   pricecatcher: extra item mappings the pack did not have (dedup by item)
#   myfcd: source-identity mapping row (none of the 8 had one; nutrition
#          itself is deliberately NOT replaced -- is_current demotion of the
#          USDA row is a separate governed decision)
#   yield_: evidenced EDIBLE_YIELD row, inserted only if the target has none
MERGE_EVIDENCE = [
    dict(
        target="SF061", expected_names={"margarine"},
        pricecatcher=[
            ("206", "MARJERIN PLANTA", "480 g", "ACCEPTED_EQUIVALENT",
             "Official PriceCatcher item 206 'MARJERIN PLANTA', unit 480g. Second brand of the same "
             "generic 'margarine' concept already represented by item 205 on SF061; 4,251 "
             "observations, 1,146 shops, 16/16 states. Merged from retired draft SF077."),
        ],
        myfcd=("MYFCD_1997", "112001", "Margarine (Marjerin)",
               "MyFCD 1997 Food ID 112001, source identity only -- SF061's current USDA-based "
               "nutrition row is left untouched (draft SF077's proposed swap is a separate governed "
               "decision). Merged from retired draft SF077."),
        yield_=(1.00, "MyFCD 112001 'Gram Edible Portion: 100g' (zero refuse) via Wayback 2017 "
                      "snapshot of article 536 (live slug now 404s); corroborated by FAO Chatfield "
                      "Table 2 'Margarine' Refuse 0%. Merged from retired draft SF077."),
    ),
    dict(
        target="SF047", expected_names={"watermelon"},
        pricecatcher=[
            ("21", "TEMBIKAI MERAH TANPA BIJI", "1kg", "EXACT",
             "Official PriceCatcher item 21 'TEMBIKAI MERAH TANPA BIJI' (seedless), unit 1kg. 928 "
             "real observations, 299 shops, 12/16 states, August 2026 panel. The seedless retail "
             "form, complementing item 20 (with seeds) already mapped on SF047. Merged from retired "
             "draft SF090."),
        ],
        myfcd=("MYFCD_1997", "106093", "Watermelon (Tembikai) ; Citrullus vulgaris",
               "MyFCD 1997 Food ID 106093, source identity only -- SF047's current USDA-based "
               "nutrition row is left untouched. Merged from retired draft SF090."),
        yield_=(0.56, "MyFCD 106093 'Gram Edible Portion: 56g' (rind), re-verified via the live .tmp "
                      "endpoint -- matches the purchased-with-rind retail form exactly. Merged from "
                      "retired draft SF090."),
    ),
    dict(
        target="SF049", expected_names={"honeydew melon", "honeydew"},
        pricecatcher=[],
        myfcd=("MYFCD_CURRENT", "R106051", "HONEYDEW (TEMBIKAI SUSU)",
               "MyFCD 'current' module, NDB R106051, published 2024-12-03 -- STRONG identity match. "
               "Source identity only; SF049's USDA-based nutrition row is left untouched. Merged "
               "from retired draft SF091."),
        yield_=(0.53, "POLICY_DEFAULT proposal pending team ratification: honeydew is not in MyFCD "
                      "1997; nearest verified MyFCD melon is watermelon 0.56 (106093) and honeydew "
                      "rind share is similar or higher -- midpoint of the 0.50-0.56 range. Merged "
                      "from retired draft SF091."),
    ),
    dict(
        target="SF050", expected_names={"red dragon fruit", "dragon fruit"},
        pricecatcher=[],
        myfcd=("MYFCD_CURRENT", "R106035", "Dragon fruit (red flesh)",
               "MyFCD 'current' module, NDB R106035, published 2024-12-03 -- STRONG identity match. "
               "Source identity only; SF050's USDA-based nutrition row is left untouched. Merged "
               "from retired draft SF092."),
        yield_=(0.65, "POLICY_DEFAULT proposal pending team ratification: red dragon fruit is not "
                      "in MyFCD 1997; literature edible portion ~60-70% (thick skin) -- midpoint. "
                      "Merged from retired draft SF092."),
    ),
    dict(
        target="SF052", expected_names={"grapes", "grape"},
        pricecatcher=[],
        myfcd=("MYFCD_1997", "106028", "Grape (Buah anggur) ; Vitis vinifera",
               "MyFCD 1997 Food ID 106028. Generic grape entry, does not distinguish red/seeded vs. "
               "green/seedless cultivars -- MODERATE identity match. Source identity only; SF052's "
               "USDA-based nutrition row is left untouched. Merged from retired draft SF089."),
        yield_=(0.95, "MyFCD 106028 'Edible Portion: 95g' (stems), re-verified via the live .tmp "
                      "endpoint. Merged from retired draft SF089."),
    ),
    dict(
        target="SF055", expected_names={"lime"},
        pricecatcher=[],
        myfcd=("MYFCD_1997", "106044", "Lime, common (Limau nipis/Limau asam) ; Citrus aurantifolia",
               "MyFCD 1997 Food ID 106044; Malay name independently corroborated by DBP PRPM. "
               "Source identity only; SF055's USDA-based nutrition row is left untouched. Merged "
               "from retired draft SF078."),
        yield_=(0.62, "POLICY_DEFAULT proposal pending team ratification: the MyFCD 106044 article "
                      "is unreachable (CMS slug defect, all recovery paths exhausted 2026-09-06); "
                      "lower bound = verified closest relative calamansi 0.54 (MyFCD 106046), limau "
                      "nipis has thinner skin -- midpoint 0.62. Merged from retired draft SF078."),
    ),
    dict(
        target="SF056", expected_names={"table salt", "fine salt", "salt"},
        pricecatcher=[],
        myfcd=("MYFCD_1997", "114037", "Salt, table (Garam)",
               "MyFCD 1997 Food ID 114037. Composition does not vary meaningfully by grain size. "
               "Source identity only; SF056's USDA-based nutrition row is left untouched. Merged "
               "from retired draft SF081."),
        yield_=(1.00, "MyFCD 114037 'Gram Edible Portion: 100g' (zero refuse), re-verified via the "
                      "live .tmp endpoint. Merged from retired draft SF081."),
    ),
    dict(
        target="SF062", expected_names={"instant whole milk powder", "instant full-cream milk powder",
                                        "milk powder"},
        pricecatcher=[],
        myfcd=("MYFCD_1997", "111012", "Milk, powder, instant, full cream (Susu tepung penuh krim)",
               "MyFCD 1997 Food ID 111012, identity confirmed via the old-site detail endpoint; "
               "correctly distinct from liquid milk (SF020) and infant formula. Source identity "
               "only; SF062's USDA-based nutrition row is left untouched. Merged from retired "
               "draft SF082."),
        yield_=(1.00, "POLICY_DEFAULT proposal pending team ratification: dry powder with no "
                      "inedible part, consistent with verified MyFCD GEP 100 for brown sugar and "
                      "table salt; no MyFCD 1997 article exists for this record. Merged from "
                      "retired draft SF082."),
    ),
]

# Verified MyFCD 'Gram Edible Portion' campaign values (2026-09-06,
# myfcd_yields_20260906.json) for pre-existing pack foods that lack an
# EDIBLE_YIELD conversion row. Inserted only where no EDIBLE_YIELD row of
# any kind exists for the food (a stronger/pre-existing row always wins).
YIELD_BACKFILLS = [
    ("SF011", 0.87, "MyFCD 105089 'Gram Edible Portion: 87g' (spinach/bayam)."),
    ("SF012", 0.72, "MyFCD 105017 'Gram Edible Portion: 72g' (cabbage/kobis)."),
    ("SF013", 0.89, "MyFCD 105018 'Gram Edible Portion: 89g' (carrot/lobak merah)."),
    ("SF014", 0.92, "MyFCD 105009 'Gram Edible Portion: 92g' (long beans/kacang panjang)."),
    ("SF016", 0.73, "MyFCD 106066 'Gram Edible Portion: 73g' (papaya/betik)."),
    ("SF018", 0.95, "MyFCD 102007 'Gram Edible Portion: 95g' (sweet potato/ubi keledek), verified directly."),
    ("SF023", 0.93, "MyFCD 102003 'Gram Edible Portion: 93g' (potato/kentang)."),
    ("SF025", 0.88, "MyFCD 105098 'Gram Edible Portion: 88g' (tomato)."),
    ("SF026", 0.95, "MyFCD 105065 'Gram Edible Portion: 95g' (onion/bawang besar)."),
    ("SF027", 0.92, "MyFCD 105037 'Gram Edible Portion: 92g' (garlic/bawang putih)."),
    ("SF028", 0.63, "MyFCD 105046 'Gram Edible Portion: 63g' (kailan/Chinese kale)."),
    ("SF046", 0.77, "MyFCD 106010 'Gram Edible Portion: 77g' (banana/pisang)."),
    ("SF069", 0.88, "MyFCD 106002 'Gram Edible Portion: 88g' (apple, red/epal merah), verified directly."),
    ("SF010", 0.77, "POLICY_DEFAULT proposal pending team ratification: MyFCD 105095 article "
                    "unreachable (CMS slug defect); higher stem-trim loss than leafy veg, Thai FCT "
                    "kangkong refuse ~25-30% -- midpoint 0.77."),
    ("SF029", 0.87, "POLICY_DEFAULT proposal pending team ratification: MyFCD 105061 article "
                    "unreachable; leafy-veg trimming, midpoint of MyFCD leaf family (spinach 0.87 / "
                    "cabbage 0.72 / kailan 0.63)."),
    ("SF030", 1.00, "POLICY_DEFAULT proposal pending team ratification: sprouts are effectively "
                    "fully edible; universal FCDB convention; MyFCD article 195 unreachable."),
]


def _ensure_reviewer(bind) -> str:
    reviewer_row = bind.execute(
        sa.text("select user_id from app_user where email_normalized = :email"),
        {"email": REVIEWER_EMAIL},
    ).fetchone()
    if reviewer_row is not None:
        return reviewer_row[0]
    return bind.execute(
        sa.text(
            "insert into app_user (user_id, email, email_normalized, password_hash, role, "
            "status, email_verified) values (gen_random_uuid(), :email, :email, "
            "'migration-created-not-a-login', 'ADMIN', 'ACTIVE', true) returning user_id"
        ),
        {"email": REVIEWER_EMAIL},
    ).fetchone()[0]


def upgrade() -> None:
    bind = op.get_bind()

    # ---- new-namespace (2026-09 rebuild) skip --------------------------------
    # SF073-SF088 in the post-rebuild namespace name entirely different foods;
    # the 201-food pack supersedes this expansion. No-op instead of seeding
    # ID collisions.
    if bind.execute(sa.text("SELECT 1 FROM canonical_food WHERE canonical_food_id = 'SF201'")).fetchone():
        return

    reviewer_id = _ensure_reviewer(bind)
    reviewed_at = REVIEWED_AT

    # ---- existence snapshots (whole tables are small) --------------------
    existing_food_names = {
        r[0]: r[1]
        for r in bind.execute(
            sa.text("select canonical_food_id, canonical_name from canonical_food")
        )
    }
    existing_aliases = {
        (r[0].lower(), r[1], r[2])
        for r in bind.execute(
            sa.text("select alias_name, language, source_system from food_alias")
        )
    }
    # Dedup mappings by (system, source id) REGARDLESS of dataset version: an
    # item code or MyFCD record must never be silently mapped to two foods.
    existing_mappings = {
        (r[0], r[1])
        for r in bind.execute(
            sa.text(
                "select source_system, source_food_id from source_food_mapping "
                "where source_system in ('PRICECATCHER', 'MYFCD')"
            )
        )
    }
    existing_nutrition = {
        (r[0], r[1], r[2])
        for r in bind.execute(
            sa.text(
                "select source_dataset_version, source_record_id, canonical_food_id "
                "from food_nutrition"
            )
        )
    }
    existing_conversions = {
        (r[0], r[1])
        for r in bind.execute(
            sa.text("select canonical_food_id, conversion_type from unit_conversion")
        )
    }

    skipped: list[str] = []

    # ---- 1) the 12 genuinely-new foods ----------------------------------
    for f in NEW_FOODS:
        sf_id = f["sf_id"]
        target_id = sf_id
        if sf_id in existing_food_names:
            if existing_food_names[sf_id].lower() != f["english_name"].lower():
                raise RuntimeError(
                    f"UNEXPECTED_IDENTITY: {sf_id} already exists as "
                    f"{existing_food_names[sf_id]!r}, expected {f['english_name']!r}. "
                    f"Refusing to overwrite an identity this migration does not recognise."
                )
            skipped.append(f"{sf_id}: already applied")
            continue  # aliases/mappings/conversions below also already applied

        bind.execute(
            sa.text(
                "insert into canonical_food (canonical_food_id, canonical_name, "
                "canonical_name_ms, category, status) values (:id, :name, :name_ms, :cat, 'ACTIVE')"
            ),
            {"id": sf_id, "name": f["english_name"], "name_ms": f["malay_name"],
             "cat": f["category"]},
        )
        existing_food_names[sf_id] = f["english_name"]

        alias_rows = [(f["english_name"], "en", "WISEBASKET_CURATED"),
                      (f["malay_name"], "ms", "WISEBASKET_CURATED"),
                      *f["aliases"]]
        for name, lang, src in alias_rows:
            key = (name.lower(), lang, src)
            if key in existing_aliases:
                skipped.append(f"{sf_id} alias {name!r} ({lang},{src}): already present")
                continue
            bind.execute(
                sa.text(
                    "insert into food_alias (canonical_food_id, alias_name, language, source_system) "
                    "values (:fid, :name, :lang, :src)"
                ),
                {"fid": target_id, "name": name, "lang": lang, "src": src},
            )
            existing_aliases.add(key)

        for item_code, item_name, unit, mapping_status, evidence in f["pricecatcher"]:
            key = ("PRICECATCHER", item_code)
            if key in existing_mappings:
                skipped.append(f"{sf_id} item {item_code}: already mapped elsewhere")
                continue
            bind.execute(
                sa.text(
                    "insert into source_food_mapping (source_system, source_dataset_version, "
                    "source_food_id, source_food_name, source_unit_or_form, canonical_food_id, "
                    "mapping_status, verification_status, review_status, evidence_note, "
                    "reviewed_by, reviewed_at) values ('PRICECATCHER', 'PriceCatcher 2026-08', "
                    ":code, :iname, :unit, :fid, :status, 'VERIFIED', 'APPROVED', :evidence, "
                    ":reviewer, :reviewed_at)"
                ),
                {"code": item_code, "iname": item_name, "unit": unit, "fid": target_id,
                 "status": mapping_status, "evidence": evidence, "reviewer": reviewer_id,
                 "reviewed_at": reviewed_at},
            )
            existing_mappings.add(key)

        dataset_version, record_id, source_name, nutrients, evidence = f["myfcd"]
        key = ("MYFCD", record_id)
        if key in existing_mappings:
            skipped.append(f"{sf_id} MyFCD {record_id}: already mapped elsewhere")
        else:
            bind.execute(
                sa.text(
                    "insert into source_food_mapping (source_system, source_dataset_version, "
                    "source_food_id, source_food_name, source_unit_or_form, canonical_food_id, "
                    "mapping_status, verification_status, review_status, evidence_note, "
                    "reviewed_by, reviewed_at) values ('MYFCD', :version, :code, :iname, NULL, "
                    ":fid, 'EXACT', 'VERIFIED', 'APPROVED', :evidence, :reviewer, :reviewed_at)"
                ),
                {"version": dataset_version, "code": record_id, "iname": source_name,
                 "fid": target_id, "evidence": evidence, "reviewer": reviewer_id,
                 "reviewed_at": reviewed_at},
            )
            existing_mappings.add(key)

        nkey = (dataset_version, record_id, target_id)
        if nkey in existing_nutrition:
            skipped.append(f"{sf_id} nutrition {record_id}: already present")
        else:
            bind.execute(
                sa.text(
                    "insert into food_nutrition (canonical_food_id, source_dataset_version, "
                    "source_record_id, basis_g, energy_kcal, protein_g, fat_g, carbohydrate_g, "
                    "fibre_g, vitamin_c_mg, quality_status, is_current) values "
                    "(:fid, :version, :code, 100, :energy, :protein, :fat, :carbs, :fibre, :vitc, "
                    "'PASS', true)"
                ),
                {"fid": target_id, "version": dataset_version, "code": record_id,
                 "energy": nutrients.get("energy_kcal"), "protein": nutrients.get("protein_g"),
                 "fat": nutrients.get("fat_g"), "carbs": nutrients.get("carbohydrate_g"),
                 "fibre": nutrients.get("fibre_g"), "vitc": nutrients.get("vitamin_c_mg")},
            )
            existing_nutrition.add(nkey)

        if f["purchase_mass"] is not None:
            source_unit, factor_g = f["purchase_mass"]
            ckey = (target_id, "PURCHASE_MASS")
            if ckey in existing_conversions:
                skipped.append(f"{sf_id} PURCHASE_MASS: already present")
            else:
                bind.execute(
                    sa.text(
                        "insert into unit_conversion (canonical_food_id, conversion_type, "
                        "source_unit, target_unit, factor, edible_yield_fraction, "
                        "production_eligible, evidence_note) values (:fid, 'PURCHASE_MASS', "
                        ":unit, 'g', :factor, NULL, true, :evidence)"
                    ),
                    {"fid": target_id, "unit": source_unit, "factor": factor_g,
                     "evidence": "PriceCatcher's own reported unit is a true, exact mass unit -- "
                                 "deterministic parse."},
                )
                existing_conversions.add(ckey)

        if f["yield_"] is not None:
            fraction, evidence = f["yield_"]
            ckey = (target_id, "EDIBLE_YIELD")
            if ckey in existing_conversions:
                skipped.append(f"{sf_id} EDIBLE_YIELD: already present")
            else:
                bind.execute(
                    sa.text(
                        "insert into unit_conversion (canonical_food_id, conversion_type, "
                        "source_unit, target_unit, factor, edible_yield_fraction, "
                        "production_eligible, evidence_note) values (:fid, 'EDIBLE_YIELD', "
                        "'purchase_mass', 'edible_mass', NULL, :fraction, true, :evidence)"
                    ),
                    {"fid": target_id, "fraction": fraction, "evidence": evidence},
                )
                existing_conversions.add(ckey)

    # ---- 2) merge incremental evidence into the 8 existing foods --------
    for m in MERGE_EVIDENCE:
        target = m["target"]
        if target not in existing_food_names:
            skipped.append(f"{target}: merge target absent on this database -- skipped")
            continue
        actual = existing_food_names[target].lower()
        if actual not in m["expected_names"]:
            raise RuntimeError(
                f"UNEXPECTED_IDENTITY: merge target {target} is {actual!r}, expected one of "
                f"{sorted(m['expected_names'])}. Refusing to merge evidence onto an "
                f"unrecognised identity."
            )

        for item_code, item_name, unit, mapping_status, evidence in m["pricecatcher"]:
            key = ("PRICECATCHER", item_code)
            if key in existing_mappings:
                skipped.append(f"{target} item {item_code}: already mapped -- not re-added")
                continue
            bind.execute(
                sa.text(
                    "insert into source_food_mapping (source_system, source_dataset_version, "
                    "source_food_id, source_food_name, source_unit_or_form, canonical_food_id, "
                    "mapping_status, verification_status, review_status, evidence_note, "
                    "reviewed_by, reviewed_at) values ('PRICECATCHER', 'PriceCatcher 2026-08', "
                    ":code, :iname, :unit, :fid, :status, 'VERIFIED', 'APPROVED', :evidence, "
                    ":reviewer, :reviewed_at)"
                ),
                {"code": item_code, "iname": item_name, "unit": unit, "fid": target,
                 "status": mapping_status, "evidence": evidence, "reviewer": reviewer_id,
                 "reviewed_at": reviewed_at},
            )
            existing_mappings.add(key)

        if m["myfcd"] is not None:
            dataset_version, record_id, source_name, evidence = m["myfcd"]
            key = ("MYFCD", record_id)
            if key in existing_mappings:
                skipped.append(f"{target} MyFCD {record_id}: already mapped -- not re-added")
            else:
                bind.execute(
                    sa.text(
                        "insert into source_food_mapping (source_system, source_dataset_version, "
                        "source_food_id, source_food_name, source_unit_or_form, canonical_food_id, "
                        "mapping_status, verification_status, review_status, evidence_note, "
                        "reviewed_by, reviewed_at) values ('MYFCD', :version, :code, :iname, NULL, "
                        ":fid, 'EXACT', 'VERIFIED', 'APPROVED', :evidence, :reviewer, :reviewed_at)"
                    ),
                    {"version": dataset_version, "code": record_id, "iname": source_name,
                     "fid": target, "evidence": evidence, "reviewer": reviewer_id,
                     "reviewed_at": reviewed_at},
                )
                existing_mappings.add(key)

        if m["yield_"] is not None:
            fraction, evidence = m["yield_"]
            ckey = (target, "EDIBLE_YIELD")
            if ckey in existing_conversions:
                skipped.append(f"{target} EDIBLE_YIELD: already present -- kept existing")
            else:
                bind.execute(
                    sa.text(
                        "insert into unit_conversion (canonical_food_id, conversion_type, "
                        "source_unit, target_unit, factor, edible_yield_fraction, "
                        "production_eligible, evidence_note) values (:fid, 'EDIBLE_YIELD', "
                        "'purchase_mass', 'edible_mass', NULL, :fraction, true, :evidence)"
                    ),
                    {"fid": target, "fraction": fraction, "evidence": evidence},
                )
                existing_conversions.add(ckey)

    # ---- 3) verified/policy yield backfills for pre-existing pack foods --
    for food_id, fraction, evidence in YIELD_BACKFILLS:
        if food_id not in existing_food_names:
            skipped.append(f"{food_id}: backfill target absent on this database -- skipped")
            continue
        ckey = (food_id, "EDIBLE_YIELD")
        if ckey in existing_conversions:
            skipped.append(f"{food_id} EDIBLE_YIELD: already present -- kept existing")
            continue
        bind.execute(
            sa.text(
                "insert into unit_conversion (canonical_food_id, conversion_type, "
                "source_unit, target_unit, factor, edible_yield_fraction, production_eligible, "
                "evidence_note) values (:fid, 'EDIBLE_YIELD', 'purchase_mass', 'edible_mass', "
                "NULL, :fraction, true, :evidence)"
            ),
            {"fid": food_id, "fraction": fraction, "evidence": evidence},
        )
        existing_conversions.add(ckey)

    if skipped:
        print(f"f19b6d84c3a7: {len(skipped)} dedup skip(s) (idempotent re-run or pre-existing):")
        for s in skipped:
            print(f"  - {s}")


def downgrade() -> None:
    bind = op.get_bind()

    # New-namespace rebuild: this migration was a no-op at upgrade time.
    if bind.execute(sa.text("SELECT 1 FROM canonical_food WHERE canonical_food_id = 'SF201'")).fetchone():
        return

    reviewer_row = bind.execute(
        sa.text("select user_id from app_user where email_normalized = :email"),
        {"email": REVIEWER_EMAIL},
    ).fetchone()
    reviewer_id = reviewer_row[0] if reviewer_row is not None else None

    new_ids = [f["sf_id"] for f in NEW_FOODS]
    for table in ("unit_conversion", "food_nutrition",
                  "source_food_mapping", "food_alias", "canonical_food"):
        bind.execute(
            sa.text(f"delete from {table} where canonical_food_id = any(:ids)"),
            {"ids": new_ids},
        )

    # Merge rows: attribute precisely (this migration's reviewer+timestamp),
    # so rows that pre-existed (and were skipped at insert time) are untouched.
    for m in MERGE_EVIDENCE:
        target = m["target"]
        pc_codes = [pc[0] for pc in m["pricecatcher"]]
        if pc_codes:
            bind.execute(
                sa.text(
                    "delete from source_food_mapping where canonical_food_id = :fid "
                    "and source_system = 'PRICECATCHER' and source_food_id = any(:codes) "
                    "and reviewed_by = :reviewer and reviewed_at = :reviewed_at"
                ),
                {"fid": target, "codes": pc_codes, "reviewer": reviewer_id,
                 "reviewed_at": REVIEWED_AT},
            )
        if m["myfcd"] is not None:
            bind.execute(
                sa.text(
                    "delete from source_food_mapping where canonical_food_id = :fid "
                    "and source_system = 'MYFCD' and source_food_id = :code "
                    "and reviewed_by = :reviewer and reviewed_at = :reviewed_at"
                ),
                {"fid": target, "code": m["myfcd"][1], "reviewer": reviewer_id,
                 "reviewed_at": REVIEWED_AT},
            )
        if m["yield_"] is not None:
            bind.execute(
                sa.text(
                    "delete from unit_conversion where canonical_food_id = :fid "
                    "and conversion_type = 'EDIBLE_YIELD' and evidence_note = :evidence"
                ),
                {"fid": target, "evidence": m["yield_"][1]},
            )

    # Backfilled yield rows are identifiable by their exact evidence notes.
    backfill_notes = [evidence for _fid, _frac, evidence in YIELD_BACKFILLS]
    bind.execute(
        sa.text(
            "delete from unit_conversion where conversion_type = 'EDIBLE_YIELD' "
            "and evidence_note = any(:notes)"
        ),
        {"notes": backfill_notes},
    )
