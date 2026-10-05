"""Category consumption budgets — Option A purchase-quantity governance.

购买量治理方案 A（CONSUMPTION_CAP_DESIGN.md §2，2026-09-04 团队定稿）：
购买量必须落在现实消耗区间内——每个食材类别的采购量有来自膳食现实的硬上限
（求解器 H5 约束的右端项），单品上限取类别预算的份额，而不是由
"吃到 RNI 140%"决定购买量。

Calibrated portions (grams per adult-equivalent per day). Children count as
0.6 adult equivalents (household_equivalent convention). headroom allows
purchases beyond pure consumption (trimming loss, prep margin).

2026-09-11 basket-realism revision (planner review: RM100/2A plan returned
2 kg flour + 1.5 kg sugar + 2 kg dried beans and no rice):
- "other" headroom 3.0 -> 1.2: sugar/oil/sauce are pantry restocks and must
  NOT be auto-stocked to triple weekly consumption every plan (reviewer rule
  3: pantry items cannot default into every weekly plan).
- carbohydrate item share 0.6 -> 0.45: a single carb item may not eat almost
  half of the category budget (2 kg flour packs under RM100 budgets).
- New: deterministic food-FAMILY tables (sugar / flour / dried-legume /
  noodle) for the solver's same-family redundancy guard (reviewer rule 4:
  white sugar + palm sugar, mung beans + soybeans are low-priority combos).
- New: conventional-staple anchor constant (reviewer rule 5: a basket must
  contain something a real household would recognise as "the staple").
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .week_floors import solo_week_floor_g

# Salty/processed consumption cap (I2 Part D): high-sodium items (salted
# fish, sauces, pastes) are condiments/accents, not staples. Weekly per-adult
# allowance is small; the cap is a CEILING (not a usage quota), applied
# through the same H5 mechanism as the core categories.
SALTY_WEEKLY_BUDGET_G_PER_ADULT = 200.0   # to be calibrated with real runs

# 2026-09-11 香料/烘焙料周限额（reviewer rule 3 的延伸）：planner review 实测
# 1 kg 鲜姜黄（SF070，vegetables 类）+ 113 g 泡打粉被买进来凑钙/铁覆盖——
# 真实家庭不会拿香料当营养支柱。与 salty 同一 H5 机制，但跨类别匹配
# （姜黄挂 vegetables，salty 那套 other-only 规则管不到它）。
# 关键词刻意用完整词组："black/white pepper" 而不是裸 "pepper"，避免误伤
# 彩椒/chilli（算蔬菜）；肉桂/八角等干香料在目录里都是 "other" 小包装。
SEASONING_WEEKLY_BUDGET_G_PER_ADULT = 100.0
# 2026-09-15 user decision (save-money batch): ALL fresh wet-market
# seasonings (ginger/garlic/galangal/turmeric/lemongrass/chili) share ONE
# weekly bucket - without it the solver stacked ~1 kg of aromatics for a
# solo household (each line floors separately, cheap calories per gram).
FRESH_SEASONING_WEEKLY_BUDGET_G_PER_ADULT = 150.0
SEASONING_NAME_KEYWORDS = (
    "turmeric", "baking powder", "baking soda", "yeast", "custard",
    "mustard seed", "fenugreek", "fennel", "cumin", "coriander seed",
    "anise", "cinnamon", "clove", "cardamom", "nutmeg",
    "black pepper", "white pepper", "candlenut", "spice",
)

# 2026-09-14 鲜椰奶独立口径（用户实测：plan 里椰奶只有 200 ml，不符合常理）。
# 根因：椰奶挂 "other" 类，40 g/人/天的库存型预算几乎被食用油占满，椰奶只剩
# 零头；而椰奶是马来家常烹饪的液体主料（咖喱/椰浆饭一餐 200-300 ml）。
# 参照 salty/seasoning 机制给独立 H5 桶，并将其从原类别桶剔除
# （不再挤压油的预算）。400 g/成人/周：2A2C 家庭 ~1.28 kg/周，容得下
# "按包液体最低 1000 ml" 的购买下限（见 LIQUID_PACK_MIN_TOTAL_G）。
COCONUT_MILK_WEEKLY_BUDGET_G_PER_ADULT = 400.0
COCONUT_MILK_NAME_KEYWORDS = ("coconut milk", "santan")

# 2026-09-16 甜食家族合并周上限（用户拍板，很严——炼乳基本出局）：炼乳
# 1-3 kg 进篮病案（1A 炼乳 500 g + 椰糖 500 g）的根因是炼乳/椰糖蛋白
# >= 1 g/100g，绕过了空热量（protein<1 & fibre<1）判定。仿 is_salty_processed
# 的成熟模式：只认 "other" 类目、canonical 英文名子串匹配、经 solver 的
# H5 机制施加合并上限。50 g x 有效人头/周：糖水/甜品是零食级点缀，不是
# B40 周篮的营养支柱；营养缺口由奶/豆腐等顶上（solver 自然转向）。
# 关键词刻意不含裸 "sugar"——白糖/椰糖已按全词组命中，而 "sugar
# confectionery" 等零食行是否纳入留待用户再拍板（家族硬上限已每计划
# 限糖 1 种）。locks/selected-presence floors 豁免（存在权 > 经济护栏）。
SWEET_WEEKLY_BUDGET_G_PER_ADULT = 50.0
SWEET_NAME_KEYWORDS = (
    "condensed",                       # sweetened condensed milk (炼乳)
    "palm sugar", "gula melaka", "gula kabung",   # 椰糖
    "white sugar", "gula putih",     # 白糖
    "brown sugar",                   # 红糖
)


def is_sweet_good(category: str, name: str) -> bool:
    """Is this food a sweet good (condensed milk / sugars)? Only "other"-
    category foods qualify, matched on the canonical English name (same
    pattern as is_salty_processed). See SWEET_WEEKLY_BUDGET_G_PER_ADULT."""
    if category not in ("other", "others"):
        return False
    n = (name or "").lower()
    return any(k in n for k in SWEET_NAME_KEYWORDS)


def is_coconut_milk(name: str) -> bool:
    """椰奶/椰浆（任何类别，跨类目匹配，同 is_seasoning_spice 的机制）。
    命中者走自己的 coconut_milk H5 桶，不再占 "other" 类预算。"""
    n = (name or "").lower()
    return any(k in n for k in COCONUT_MILK_NAME_KEYWORDS)


# 2026-09-17 v5-2 (user decision): rice is the Malaysian staple anchor;
# noodles/flour/oats/bread/instant noodles are the SIDE staple, capped
# weekly so cheap dry carbs cannot stack into the energy target (2A2C
# RM200 previously bought 9.8 kg of carbs). 80 g x effective person x 7
# days (weekly product - days is not plumbed into the model builder, same
# convention as the sweet-goods cap). Recalibrated 80 -> 120 g the same day
# (PM review): 80 g collapsed the FAMILY energy ceiling below the target
# (idle-money INFEASIBLE on 2A2C); 120 g restores the corridor.
NON_RICE_CARB_WEEKLY_BUDGET_G_PER_ADULT = 120.0 * 7
RICE_FAMILY_KEYWORDS = ("rice", "beras", "glutinous", "basmati")
# Processed rice-family forms count as SIDE staples (the cap applies):
RICE_PROCESSED_KEYWORDS = (
    "flour", "noodle", "vermicelli", "bihun", "kuey teow", "kuey-teow",
    "hor fun", "horfun", "instant", "glutinous",
)

# v5-2 (user decision): dry spices (curry powder / asam paste / whole
# spices) are month-long pantry items even though they are sold by the
# gram - hard 100 g per plan (a Baba's curry powder pack is the real unit).
# 词表刻意不含 fresh seasonings（姜黄/姜/蒜按 25-50g 周步进，不是 500g
# 堆叠元凶）与烘焙项（酵母/泡打粉）——只抓咖喱粉/亚参/整粒香料。
DRY_SPICE_WEEKLY_CAP_G = 100
DRY_SPICE_PANTRY_KEYWORDS = (
    "curry powder", "asam", "tamarind",
    "mustard seed", "fenugreek", "fennel", "cumin", "coriander seed",
    "anise", "cinnamon", "clove", "cardamom", "nutmeg",
    "black pepper", "white pepper", "candlenut",
)

# v5-6a (2026-09-17, user decision): cooking oil caps at ONE litre per week
# regardless of household size (fixed, not per-person).
OIL_WEEKLY_CAP_G = 1000


def is_dry_spice_pantry(name: str) -> bool:
    """v5-2: month-long dry-spice pantry item for the 100 g/plan hard cap.
    Any category (curry powder is 'other', asam paste may sit in vegetables);
    fresh seasonings and baking items deliberately excluded."""
    n = (name or "").lower()
    return any(k in n for k in DRY_SPICE_PANTRY_KEYWORDS)


# 2026-09-17 (B1, real-device feedback): instant / cup noodles are a
# convenience backup, not a weekly staple - 2 adults were suggested 20
# packs. At most ~this many packs per effective person per week (selected
# journeys only; H5 carb budgets still apply underneath).
PROCESSED_CARB_PACKS_PER_ADULT_WEEK = 7.0


def is_processed_carb(category: str, name: str) -> bool:
    """Instant / cup noodle-type processed carbs (pack convenience food).
    Fresh noodles (yellow noodles, kuey teow, vermicelli) are cooking
    staples and are NOT caught."""
    if category != "carbohydrate":
        return False
    n = (name or "").lower()
    return ("instant" in n and "noodle" in n) or "cup noodle" in n


# 2026-09-17 (B3): same-class fresh-meat species classification for the
# dedup soft penalty (whole chicken + chicken whole leg in one basket).
# Keyword order matters: first match wins, so specific names come first.
MEAT_SPECIES_KEYWORDS = (
    ("poultry", "chicken"), ("poultry", "duck"), ("poultry", "turkey"),
    ("red_meat", "beef"), ("red_meat", "mutton"), ("red_meat", "lamb"),
    ("red_meat", "pork"), ("red_meat", "goat"),
    ("fish", "tenggiri"), ("fish", "kembung"), ("fish", "selar"),
    ("fish", "sardine"), ("fish", "mackerel"), ("fish", "tilapia"),
    ("fish", "catfish"), ("fish", "snapper"), ("fish", "threadfin"),
    ("fish", "wolf herring"), ("fish", "gelama"), ("fish", "kerapu"),
    ("fish", "senangin"), ("fish", "terubok"), ("fish", "pari"),
    ("fish", "tuna"), ("fish", "bilis"), ("fish", "anchovy"),
    ("fish", "herring"), ("fish", "goldband"), ("fish", "cincaru"),
    ("fish", "ikan"), ("fish", "fish"),
    ("seafood", "prawn"), ("seafood", "shrimp"), ("seafood", "crab"),
    ("seafood", "squid"), ("seafood", "cuttlefish"), ("seafood", "clam"),
)


def meat_species(name: str):
    """-> (meat_class, species_key) for fresh-meat/fish/seafood names, else
    (None, None). Eggs / legumes / dairy are not meat classes and return
    None (no dedup - the B40 protein ladder needs them together)."""
    n = (name or "").lower()
    # Exclusions FIRST: "chicken eggs" must not match poultry-chicken, soy
    # / dairy / legumes are ladder staples not meat species.
    if any(k in n for k in (
            "egg", "telur", "milk", "susu", "cheese", "yoghurt",
            "yogurt", "dhal", "lentil", "tofu", "tempeh")):
        return None, None
    for cls, key in MEAT_SPECIES_KEYWORDS:
        if key in n:
            return cls, key
    return None, None


def is_rice_family(category: str, name: str) -> bool:
    """Is this a PLAIN-rice staple (exempt from the non-rice carb cap)?
    Only carbohydrate-category foods qualify, and processed rice-family
    forms (rice flour / rice noodles / bihun / kuey teow / instant) are
    side staples - the cap applies to them (2026-09-17 PM: the v1
    exemption let the solver dodge the cap by shuffling carbs into
    glutinous rice + rice vermicelli, so total carbs never fell)."""
    if category not in ("carbohydrate", "staples"):
        return False
    n = (name or "").lower()
    if not any(k in n for k in RICE_FAMILY_KEYWORDS):
        return False
    return not any(k in n for k in RICE_PROCESSED_KEYWORDS)


# 2026-09-14 per-line purchase floor (user rule, verbatim: "nothing in the
# week plan may total less than 1000 g or 1000 ml"): EVERY purchase line
# totals >= 1000 g/ml. PR #136 narrowed this to pack liquids + by-weight
# meat/seafood without a mandate; the user called out the dropped scope.
# Now applies uniformly: pack solids (tofu 300 g -> 4 packs = 1200 g),
# per-piece packs (egg tray ~580 g -> 2 packs = 20 eggs), per-piece
# produce (apple 180 g -> 6 pieces = 1080 g). Dry pantry forms (milk
# powder) are no longer exempt: 250 g -> 4 packs. Minimum packs =
# ceil(1000 / pack_grams), at least 1 pack.
PACK_MIN_TOTAL_G = 1000

# ---------------------------------------------------------------------------
# 2026-09-15 user decision (save-money batch): the WHOLE weekly-basket rule
# set keyed by household size is ONE explicit hard-coded table - purchase
# floors, fresh-seasoning floors AND basket variety - not a formula.
# Rationale (user intent, 2026-09-15): "4 people buying 1000 g lines is
# fine; the same 1000 g for one person is unreasonable - and the KINDS of
# food a single person buys are different too". Effective persons =
# adults + 0.6 * children (the solver convention, see
# solver._effective_persons). Rows are
#   (up_to_effective_persons, pack/by-weight floor g, fresh seasoning g,
#    basket kind soft floor, basket kind soft cap)
# and the FIRST row whose bucket covers the household wins. Every value is
# individually reviewable in place. Measured weekly baskets (ns_rebuild
# personas, 2026-09-15): 1A at floor 250 g / 6-9 kinds -> RM85/wk (floor
# 500 g -> RM139, rejected as abnormal for one person; the old 1000 g
# forced a family-size pantry onto a solo household). The family bucket
# (2+ adults) keeps the original 2026-09-14 rules unchanged.
# 2026-09-16 W5 user decision: the solo kind caps were the 1A-coverage
# bottleneck (9 kinds reached only 68.6% coverage) - kind CAPS raised to
# 12 (1A) / 15 (1A1C); kind FLOORS, pack floors and seasoning floors stay.
HOUSEHOLD_BASKET_RULES_TABLE: Tuple[Tuple[float, int, int, int, int], ...] = (
    (1.25, 250, 100, 6, 12),     # 1 adult alone: solo week - small lines, more kinds
    (1.75, 400, 150, 8, 15),     # 1 adult + 1 small child
    (99.0, 1000, 250, 10, 15),   # 2+ adults: original 2026-09-14 family rules
)


def _rules_row(persons: float = 2.0) -> Tuple[float, int, int, int, int]:
    for row in HOUSEHOLD_BASKET_RULES_TABLE:
        if persons <= row[0]:
            return row
    return HOUSEHOLD_BASKET_RULES_TABLE[-1]


def pack_min_total_g(persons: float = 2.0) -> int:
    """Pack / by-weight purchase floor (g) for the household size - a
    hard-coded table row, NOT a formula (see HOUSEHOLD_BASKET_RULES_TABLE)."""
    return _rules_row(persons)[1]


def fresh_seasoning_min_g(persons: float = 2.0) -> int:
    """Fresh-seasoning purchase floor (g) for the household size (table)."""
    return _rules_row(persons)[2]


def basket_kind_floor(persons: float = 2.0) -> int:
    """Soft minimum number of distinct food kinds in the week plan (table)."""
    return _rules_row(persons)[3]


def basket_kind_cap(persons: float = 2.0) -> int:
    """Soft maximum number of distinct food kinds in the week plan (table)."""
    return _rules_row(persons)[4]


def pack_min_packs(pack_grams: int, persons: float = 2.0) -> int:
    """Minimum purchase packs for a pack-based food: total >= the household
    floor (>= 1 pack). The default persons=2.0 (family bucket) keeps every
    legacy call site unchanged."""
    return max(1, -(-pack_min_total_g(persons) // max(1, int(pack_grams))))


def food_week_floor_g(food_id: str, persons: float = 2.0) -> Optional[int]:
    """2026-09-16 PM proposal (user approved): per-food weekly purchase
    floor - the curated solo-adult value (week_floors.csv, kept in CODE not
    the DB) scaled linearly by effective persons (beef 0.5 kg solo -> 1 kg
    for 2 adults, 0.8 kg for 1A1C). None when the food has no curated row,
    so callers fall back to the household-size table floor."""
    base = solo_week_floor_g(food_id)
    if base is None:
        return None
    return max(1, int(round(base * persons)))


# Back-compat aliases (PR #136 liquid-specific names; the floor semantics
# are universal now, see above).
LIQUID_PACK_MIN_TOTAL_G = PACK_MIN_TOTAL_G
liquid_min_packs = pack_min_packs

# 2026-09-14 贵蛋白单品花费上限（用户反馈：B40 画像一周买 RM60 牛肉太奢侈）。
# 单价 >= RM2.50/100g 的蛋白（牛肉/羔羊肉/明虾等）单品花费 <= 预算的 15%
# （RM200 -> 单样 <= RM30 ~ 790 g 牛肉）。presence floor（1000 g ~ RM38）
# 会强行买回勾选项（存在权 > 经济护栏），该上限只约束 solver 的自由追加量；
# 蛋白由鸡/蛋/豆等平价蛋白补齐（H5 蛋白预算不变）。locks 用户锁量豁免。
PREMIUM_PROTEIN_PRICE_RM_PER_100G = 2.50
PREMIUM_PROTEIN_SPEND_SHARE = 0.15
# 2026-09-15 expensive-line gate (save-money batch): the per-gram "dear"
# threshold for the tight-budget free-add gate in solver._build_primary_model
# - a food pricier than this per 100 g whose minimum purchase line also
# breaches 15% of the weekly budget may not be solver-added (picks/locks
# exempt). Below this price even a >15%-of-budget line stays buyable (a
# cheap 10 kg rice bag is normal, not a luxury). RM1.80 sits above the
# staple proteins (chicken thigh ~RM1.20/100 g, eggs ~RM0.97) and catches
# the dear filler traps (dried shrimp RM8.33, cheese RM4.74, dried chili
# RM2.20, grapes RM1.88).
TIGHT_GATE_PRICE_RM_PER_100G = 1.80


def is_premium_protein(category: str, price_rm_per_100g) -> bool:
    return (category == "protein"
            and price_rm_per_100g is not None
            and price_rm_per_100g >= PREMIUM_PROTEIN_PRICE_RM_PER_100G)


def premium_protein_cap_g(budget_rm: float, price_rm_per_100g: float) -> int:
    """贵蛋白单品克数上限：budget x 15% 按单价换算成克。"""
    return int(budget_rm * PREMIUM_PROTEIN_SPEND_SHARE * 100.0
               / max(price_rm_per_100g, 0.01))

# 每人每日消耗标定（成人当量，g/day；依据见设计文档 §2.1 表格）。
PORTION_G_PER_ADULT_DAY = {
    "carbohydrate": 260.0,   # DOSM 人均米 ~80 kg/年 ≈ 220 g/天（生重）+ 面/面包余量
    "staples": 260.0,        # carbohydrate 的别名键（旧命名兼容）
    "protein": 160.0,        # 鱼禽蛋豆合计约 120-180 g/人/天
    "vegetables": 130.0,     # ~100 g/人/天 + 择菜损耗余量
    "fruit": 100.0,          # ~80 g/人/天 + 余量
    "other": 40.0,           # 油盐糖酱：库存型采购（一瓶用数周），不按周消耗等比
    "others": 40.0,          # other 的别名键（旧命名兼容）
    # salty 以周预算标定：200 g/成人/周 ÷ 7（不是按日消耗等比，与 other 同理）。
    "salty": SALTY_WEEKLY_BUDGET_G_PER_ADULT / 7.0,
    # seasoning 同理：100 g/成人/周的香料/烘焙料硬上限（2026-09-11）。
    "seasoning": SEASONING_WEEKLY_BUDGET_G_PER_ADULT / 7.0,
    # 2026-09-15: ALL fresh seasonings share ONE bucket (see
    # FRESH_SEASONING_WEEKLY_BUDGET_G_PER_ADULT).
    "fresh_seasoning": FRESH_SEASONING_WEEKLY_BUDGET_G_PER_ADULT / 7.0,
    # 椰奶周预算（2026-09-14，见 is_coconut_milk）。
    "coconut_milk": COCONUT_MILK_WEEKLY_BUDGET_G_PER_ADULT / 7.0,
    # 甜食合并周上限（2026-09-16 用户拍板 50 g/成人/周，见 is_sweet_good）。
    "sweet": SWEET_WEEKLY_BUDGET_G_PER_ADULT / 7.0,
}

# 购买余量系数：允许购买量超出"纯消耗"的比率（设计 §2.1）。
CATEGORY_HEADROOM = {
    "carbohydrate": 1.0, "staples": 1.0,
    "protein": 1.15,
    "vegetables": 1.20,
    "fruit": 1.20,
    "other": 1.2, "others": 1.2,   # 2026-09-11: was 3.0 — pantry items must
    "salty": 1.0,                    # not be auto-restocked every weekly plan
    "seasoning": 1.0,                # 消耗上限即购买上限（香料，无库存余量）
    "fresh_seasoning": 1.0,          # 2026-09-15: shared bucket, no pantry headroom
    "coconut_milk": 1.0,             # 2026-09-14: 烹饪主料，消耗即购买上限
    "sweet": 1.0,                    # 2026-09-16: 零食级点缀，消耗即购买上限
}

# 单品上限 = 类别预算 × 份额（设计 §2.2）。防单一食材霸占类别总量
# （实测：无份额时芥兰一个菜可吃满 3 kg 蔬菜预算；加 50% 份额后 ≤1.85 kg）。
# "other" 类不设份额——库存型食材天然受包数限制，直接限包数。
# 2026-09-11: carbohydrate share 0.6 -> 0.45（紧预算下 2 kg 面粉包占满份额）。
ITEM_CAP_SHARE = {
    "carbohydrate": 0.45, "staples": 0.45,
    "protein": 0.6,
    "vegetables": 0.5,
    "fruit": 0.5,
}

FILLER_WEEKLY_CAP_G = 1000
# 命中的填充食材名单（2026-09-13 九选画像复盘：2 kg 花生吃满蛋白 H5 预算，
# Calcium 缺口 20% 且现金花不出去）。仅限 protein/carbohydrate 类——蔬菜类的
# 四季豆等不受影响；1A 紧预算画像的蛋白预算本身只有 ~1.3 kg，1 kg 帽不冲突。
FILLER_NAME_KEYWORDS = ("peanut", "dhal", "lentil", "bean", "noodle")
FILLER_CAP_CATEGORIES = ("protein", "carbohydrate", "staples")


def filler_cap_g(name: str, category: str) -> int | None:
    """廉价热量填充食材的单品周上限（克）；非填充食材返回 None。"""
    if category not in FILLER_CAP_CATEGORIES:
        return None
    n = (name or "").lower()
    if any(k in n for k in FILLER_NAME_KEYWORDS):
        return FILLER_WEEKLY_CAP_G
    return None


# 2026-09-11 主食/蛋白单品上限的"整包豁免"：份额上限不能把唯一合法规格的
# 主粮挡在计划外（如 2 kg 装米略高于 45% 份额）。对 carbohydrate/protein，
# 单品上限 = max(份额上限, 一个整包)；蔬菜/水果不豁免（大包装蔬菜真实地
# 吃不完）。H5 类别预算与 35% 能量份额护栏仍然兜底。
PACK_EXEMPT_CATEGORIES = ("carbohydrate", "staples", "protein")

# "other" 类单品包数上限（库存型食材，设计 §2.2 / 风险 R3）。
# 小包装调味料（pack < 300 g：椰浆 200 / 咖喱粉 250 级）限 1 包——真实家庭
# 一周用不完 2 包同种调味料；2026-09-04 实测 2 包漏洞被营养密度钻空子：
# 咖喱粉（iron 19.1mg/100g）按 pantry 余量买 500 g，占 RM100 紧张篮子 14%，
# 挤占主食预算。300 g 及以上（饼干/酱料/盐/奶粉/油）保持 2 包——零食和
# 烹饪酱料一周 2 包是真实消费模式，且不被营养密度利用（营养素密度低）。
ITEM_CAP_OTHER_MAX_PACKS = 2
ITEM_CAP_OTHER_SMALL_PACK_G = 300
ITEM_CAP_OTHER_SMALL_MAX_PACKS = 1

# H7 咸货判定（I2 Part D）：咸鱼类/酱料/虾酱等高钠加工品在目录里挂 "other"
# 类。确定性关键词映射（canonical 英文名，子串匹配，无 LLM、无需新 DB 列）；
# 只有 "other" 类食材可能被判为 salty——核心类别的新鲜食材不因名字重分类。
SALTY_NAME_KEYWORDS = ("salt", "sauce", "paste", "belacan", "cincalok", "budu")


# 未知类别的回落标定（取蔬菜档的中位值；正常数据只有少量标准类别）。
_FALLBACK_PORTION_G = 130.0
_FALLBACK_HEADROOM = 1.20
_FALLBACK_ITEM_SHARE = 0.5


def category_budget_g(category: str, adults: int, children: int, days: int) -> int:
    """类别购买预算（克）：portion × headroom × (adults + 0.6×children) × days。

    即硬约束 H5 的右端项（整数化到克）：
    Σ packs_i × x_i (i ∈ cat) ≤ category_budget_g(cat, ...)（设计 §2.2）。"""
    portion = PORTION_G_PER_ADULT_DAY.get(category, _FALLBACK_PORTION_G)
    headroom = CATEGORY_HEADROOM.get(category, _FALLBACK_HEADROOM)
    household_equivalent = adults + 0.6 * children
    return int(portion * headroom * household_equivalent * days)


def item_cap_g(category: str, adults: int, children: int, days: int, pack_grams: int) -> int:
    """单品购买上限（克）：类别预算的份额；"other" 类限包数
    （小包装调味料 1 包，大包装库存品 2 包，见 ITEM_CAP_OTHER_* 注释）。
    carbohydrate/protein 取 max(份额, 一个整包)——整包豁免见
    PACK_EXEMPT_CATEGORIES 注释。"""
    if category in ITEM_CAP_SHARE:
        cap = int(
            category_budget_g(category, adults, children, days) * ITEM_CAP_SHARE[category]
        )
        if category in PACK_EXEMPT_CATEGORIES:
            cap = max(cap, max(1, pack_grams))
        return cap
    if category in ("other", "others"):
        max_packs = (
            ITEM_CAP_OTHER_SMALL_MAX_PACKS
            if 0 < pack_grams < ITEM_CAP_OTHER_SMALL_PACK_G
            else ITEM_CAP_OTHER_MAX_PACKS
        )
        return max_packs * max(1, pack_grams)
    return int(
        category_budget_g(category, adults, children, days) * _FALLBACK_ITEM_SHARE
    )


def is_salty_processed(category: str, name: str) -> bool:
    """H7: is this food a salty/processed condiment (salty-fish, sauces,
    pastes)? Only "other"-category foods qualify; matched on the canonical
    English name (see SALTY_NAME_KEYWORDS)."""
    if category not in ("other", "others"):
        return False
    n = (name or "").lower()
    return any(k in n for k in SALTY_NAME_KEYWORDS)


def is_seasoning_spice(category: str, name: str) -> bool:
    """2026-09-11: is this food a dry spice / baking ingredient? Matches ANY
    category (turmeric is curated as 'vegetables' but is bought by the gram),
    unlike is_salty_processed. See SEASONING_NAME_KEYWORDS for the deliberate
    full-phrase choices (no bare 'pepper' - bell/chilli peppers are veg)."""
    n = (name or "").lower()
    return any(k in n for k in SEASONING_NAME_KEYWORDS)


def packs_for_grams(grams: float, pack_grams: int) -> int:
    """Whole retail packs needed to cover `grams` (round up, at least 1).

    Mirrors the solver's whole-pack purchasing so swap previews match what a
    re-plan would actually buy."""
    return max(1, -(-int(round(grams)) // max(1, int(pack_grams))))


# ---------------------------------------------------------------------------
# 2026-09-11 basket-realism: food families, conventional staples, pack choice
# ---------------------------------------------------------------------------

# 确定性食物族关键词表（canonical 英文名，子串匹配，小写；与 is_salty_processed
# 同一模式，无 LLM、无需新 DB 列）。用途：求解器同族冗余治理
# （reviewer rule 4: white sugar + palm sugar、mung beans + soybeans 这类
# 组合在紧预算下优先级应非常低）。
# - HARD_CAP_ONE_FAMILIES: 每计划同族最多 1 种（硬约束）——真实家庭一次只买
#   一种糖 / 一种面粉；这两种是 pantry 型，营养重叠度最高。
# - SOFT_FAMILIES: 同族第 2 种起软罚（见 solver.FAMILY_DUPLICATE_PENALTY）——
#   豆类/面类买两种并非不可能，但不该是紧预算下的默认结果。
# 注意关键词选择刻意保守（"soybean" 而非 "soya"，避免把 soya sauce 误归
# 豆类；"noodle" 覆盖 fresh/instant noodles，不再加 "mee" 防误伤）。
FOOD_FAMILY_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "sugar": ("sugar", "gula"),
    "flour": ("flour", "tepung"),
    "dried_legume": (
        "mung bean", "soybean", "soya bean", "red bean", "green bean",
        "azuki", "dhal", "lentil", "chickpea", "kidney bean", "peanut",
    ),
    "noodle": ("noodle", "kuey teow", "bihun", "vermicelli"),
}
HARD_CAP_ONE_FAMILIES: Tuple[str, ...] = ("sugar", "flour")
SOFT_FAMILIES: Tuple[str, ...] = ("dried_legume", "noodle")

# 常规主粮（conventional staple）：真实家庭认知里"当饭吃"的东西。
# 2026-09-11 截图病案：篮子 carb 只有 self-raising flour（2 kg）——数学上
# 是碳水，但没人拿自发面粉当一周主粮。锚点约束/可行性检查用它区分
# "面粉型碳水"与"米饭面条型主食"。
CONVENTIONAL_STAPLE_KEYWORDS: Tuple[str, ...] = (
    "rice", "noodle", "bread", "pasta", "bihun",
    "vermicelli", "kuey teow", "porridge",
)
# 主粮锚点量（g/成人当量/天）：篮子里至少一种常规主粮达到这个量，
# 才算"这一周的饭有着落"。取碳水日标定 260 g 的 ~35%——够真实但不被
# 35% 单品能量份额护栏误伤（米饭面条能量密度 ~110-350 kcal/100 g）。
STAPLE_ANCHOR_G_PER_ADULT_DAY = 90.0


def food_family(name: str) -> Optional[str]:
    """Return the food-family key for a canonical English name, or None.
    First matching family wins; a name can belong to at most one family by
    construction of the (deliberately non-overlapping) keyword table."""
    n = (name or "").lower()
    for family, keywords in FOOD_FAMILY_KEYWORDS.items():
        if any(k in n for k in keywords):
            return family
    return None


def is_conventional_staple(category: str, name: str) -> bool:
    """Is this food a 'conventional staple' (rice/noodle/bread family)?
    Only carbohydrate-category foods qualify — the protein- or other-category
    foods that happen to match a keyword (e.g. 'rice flour' as a seasoning
    base is NOT the household staple) are excluded by category."""
    if category not in ("carbohydrate", "staples"):
        return False
    n = (name or "").lower()
    return any(k in n for k in CONVENTIONAL_STAPLE_KEYWORDS)


def staple_anchor_g(adults: int, children: int, days: int) -> int:
    """主粮锚点量（克）= 90 g × 成人当量 × 天数（见常量注释）。"""
    return int(STAPLE_ANCHOR_G_PER_ADULT_DAY * (adults + 0.6 * children) * days)


def select_pack(
    pack_options: List[Tuple[int, str]],
    category: str,
    adults: int,
    children: int,
    days: int,
) -> Tuple[int, str]:
    """2026-09-11 多规格选择：一个食物在 DB 里可能有多条 PURCHASE_MASS
    （如鸡蛋 10/20/30 粒装）。选接近该家庭消耗量的规格：
    取不超过单品消耗上限的最大包装；若都超过则取最小包装
    （整包购买下小包总是更安全）。pack_options 为 [(grams, label), ...]。

    为什么不让求解器自己选规格：价格解析是每食物一个代表价，规格间没有
    可靠价差数据；把规格选择权放在候选加载层，求解器模型保持不变。
    """
    if not pack_options:
        return (50, "")
    # Deliberately WITHOUT the PACK_EXEMPT whole-pack bump: exemption exists
    # so the SOLVER may keep one legit pack above the share cap; pack CHOICE
    # should still start from the household-scale share cap (otherwise a
    # 10 kg rice row would always win 'largest fitting pack').
    if category in ITEM_CAP_SHARE:
        cap = int(category_budget_g(category, adults, children, days)
                   * ITEM_CAP_SHARE[category])
    else:
        cap = item_cap_g(category, adults, children, days,
                         max(p[0] for p in pack_options))
    fitting = sorted((p for p in pack_options if p[0] <= cap),
                     key=lambda p: p[0])
    if fitting:
        return fitting[-1]          # 不超上限的最大包
    return min(pack_options, key=lambda p: p[0])  # 都超 -> 最小包


# ---------------------------------------------------------------------------
# By-weight purchase (user decision 2026-09-13): fresh meat & seafood are
# sold by weight at Malaysian wet markets and butcher counters, not in fixed
# retail packs. The candidate service swaps these foods' retail pack for a
# fine purchase step; the solver's model is linear in pack counts, so the
# purchase becomes effectively continuous weight priced at price_rm_per_100g
# (e.g. 400 g chicken at RM 3.48/250 g costs 3.48/250*400 - exactly the
# user's rule). Eggs, dairy, legumes, canned and dried goods keep pack-based
# purchase.
# ---------------------------------------------------------------------------
BY_WEIGHT_STEP_G = 25
BY_WEIGHT_MIN_PURCHASE_G = 1000  # 2026-09-14 user decision (supersedes the
# 500 g rule from earlier the same day): minimum 1000 g of by-weight fresh
# meat/seafood per week-plan line (a family does not plan 500 g of beef for
# the week). 40 steps of 25 g.


def by_weight_min_steps(persons: float = 2.0) -> int:
    """Whole-step floor for one by-weight purchase (household-size table
    row: 250 g at 1 adult = 10 steps; 1000 g family = 40 steps)."""
    return max(1, -(-pack_min_total_g(persons) // BY_WEIGHT_STEP_G))


# Eligible fresh meat & seafood only (the catalog_eligible subset of the
# protein category). Deliberately excluded: eggs (sold per piece), milk /
# yogurt / soy milk (cartons), legumes (packaged), canned fish, cheese
# slices, dried anchovy/shrimp/squid (seasoning-scale usage, stay pack-based).
BY_WEIGHT_FOOD_IDS = frozenset({
    # red meat & poultry
    "SF001", "SF002", "SF003", "SF004", "SF005", "SF006", "SF008",
    # (SF009 pork (lean & fat) BLOCKED 2026-09-30: consolidated into SF008 pork belly)
    "SF013", "SF014", "SF015", "SF016", "SF017",
    # fresh fish, prawns, crab, squid
    "SF022", "SF023", "SF024", "SF025", "SF027", "SF028", "SF030", "SF032",
    "SF034", "SF035", "SF036", "SF037", "SF039", "SF042", "SF043", "SF046",
    "SF050",
    # loose dried goods (2026-09-16 user decision): dried-goods stalls scoop
    # and weigh these from sacks - registered packs are not the real unit
    "SF051", "SF052", "SF053", "SF060",
})

# 2026-09-16 user decision (scope ① of the by-weight analysis): ALL fresh
# produce is sold loose by weight at Malaysian wet markets (and supermarket
# weigh counters) - the registered 1 kg pack forced exactly the same
# absurdity as the 1 kg lime (a 1A solo plan got 1 kg of carrot). The whole
# vegetables and fruit categories are therefore by-weight; per-piece fruits
# (apple/orange/lai/lime) keep their curated piece-weight-derived RM/100g
# rate, which is honest at a weigh counter. Branded/packaged goods (cans,
# UHT, formula, snacks, bottled sauces) are NEVER by-weight - no store
# sells 600 g of canned sardine, and linear extrapolation would underprice
# small quantities (CC3 honesty).
BY_WEIGHT_CATEGORIES = frozenset({"vegetables", "fruit"})


def is_by_weight_food(food_id: str, category: str, name: str = "") -> bool:
    """Single source for by-weight semantics: curated meat/seafood/dried-
    goods ids, or any fresh-produce category, or a fresh seasoning. The
    candidate service swaps the purchase unit to 25 g steps for these."""
    if food_id in BY_WEIGHT_FOOD_IDS:
        return True
    if category in BY_WEIGHT_CATEGORIES:
        return True
    return is_fresh_seasoning(category, name)

# ---------------------------------------------------------------------------
# 2026-09-15 fresh seasonings are weighed loose (user decision, part of the
# save-money focus): ginger / garlic / fresh turmeric / galangal / lemongrass
# / fresh chili are sold by weight at Malaysian wet markets, so the universal
# 1000 g purchase floor is unrealistic - one person does not buy 1000 g of
# ginger for a week (and its registered retail pack happens to be 1 kg, so
# the blanket floor forced exactly 1 kg - one line eating a 1A household's
# entire ~1092 g weekly vegetable H5 budget). Same mechanism as by-weight
# fresh meat/seafood (candidate service swaps the purchase unit for a fine
# 25 g step priced linearly at price/100g), but the minimum purchase is
# 250 g (10 steps). Vegetables category only: turmeric powder / dried chili /
# chili sauce and other dry/processed "other" forms are untouched (whole-pack
# purchase + 1000 g floor). Note "turmeric" also matches
# SEASONING_NAME_KEYWORDS (100 g/adult/week H5 bucket) - fresh turmeric stays
# double-capped under the 2026-09-11 rule; unchanged here.
# 2026-09-16 名单扩展（用户拍板）：小葱头 shallot / 咖喱叶 curry leaves /
# 青柠 lime 同样按湿货调味料的量购买，且不再占 vegetables/fruit 的 H5
# 类目桶（1A 病案：蔬菜桶 1075/1092 g 被胡萝卜+姜黄+小葱头占满，绿叶菜被
# 挤进 worth）。青柠从水果桶移入调味桶后仍按颗计价（by-weight，F 项口径），
# 营养覆盖照常计入——只是不占类目购买预算。辣辣椒类（chili 词组）维持
# 2026-09-15 判定不变。"lime" 子串只命中 lime/calamansi lime，无误伤。
FRESH_SEASONING_MIN_PURCHASE_G = 250
FRESH_SEASONING_NAME_KEYWORDS = (
    "ginger", "garlic", "turmeric", "galangal", "lemongrass", "chili",
    "shallot", "curry leaf", "curry leaves", "lime",
)


def is_fresh_seasoning(category: str, name: str) -> bool:
    """Fresh wet-market seasonings (vegetables AND fruit categories - lime
    moved in 2026-09-16; canonical English name substring match). Matched
    foods are bought by weight in 25 g steps with the household-size floor
    (candidate service swaps the purchase unit) and are bound by the shared
    fresh_seasoning H5 bucket instead of their original category bucket."""
    if category not in ("vegetables", "fruit"):
        return False
    n = (name or "").lower()
    return any(k in n for k in FRESH_SEASONING_NAME_KEYWORDS)


def fresh_seasoning_min_steps(persons: float = 2.0) -> int:
    """Whole-step floor for one fresh-seasoning purchase (household-size
    table row: 100 g at 1 adult = 4 steps; 250 g family = 10 steps)."""
    return max(1, -(-fresh_seasoning_min_g(persons) // BY_WEIGHT_STEP_G))
