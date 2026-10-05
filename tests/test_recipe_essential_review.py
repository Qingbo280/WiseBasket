"""Offline audit of all 125 optional ingredients in the 35-recipe seed."""

from collections import Counter

import sqlalchemy as sa

from migrations.versions import f2a3b4c5d6e7_review_recipe_essentials as review
from migrations.versions import g3a4b5c6d7e8_review_legacy_recipe_seasonings as legacy_review
from migrations.versions.v4w5x6y7z8a9_prioritize_staples_over_seasonings import SEASONING_ROWS
from migrations.versions.p3q4r5s6t7u8_seed_epic5_35_recipe_collection import INGREDIENTS, RECIPES


def test_optional_audit_counts_and_recipe_scope():
    original_optional = {(recipe_id, food_id) for recipe_id, food_id, required, _, _ in INGREDIENTS
                         if not required}
    promoted = {(recipe_id, food_id) for food_id, recipe_ids in review.PROMOTION_RECIPE_IDS.items()
                for recipe_id in recipe_ids}
    assert len(RECIPES) == 35
    assert len(original_optional) == 125
    assert len(promoted) == 85
    assert promoted <= original_optional
    assert set(review.ESSENTIAL_BASE_G) == set(review.PROMOTION_RECIPE_IDS)
    assert len(original_optional - promoted) == 40
    assert Counter(food_id for _, food_id in promoted) == {
        "SF120": 33, "SF069": 23, "SF056": 13, "SF071": 8,
        "SF054": 5, "SF148": 2, "SF060": 1,
    }
    assert {recipe_id for recipe_id, food_id in promoted if food_id == "SF120"} == set(review.OIL_RECIPE_IDS)
    assert {recipe_id for recipe_id, _, _, _, _ in INGREDIENTS} - set(review.OIL_RECIPE_IDS) == {
        "garlic-spinach-stir-fry", "steamed-egg",
    }


def test_migration_promotes_only_reviewed_rows_and_round_trips(monkeypatch):
    engine = sa.create_engine("sqlite:///:memory:")
    metadata = sa.MetaData()
    ingredients = sa.Table(
        "recipe_catalog_ingredient", metadata,
        sa.Column("recipe_id", sa.String(), nullable=False),
        sa.Column("canonical_food_id", sa.String(), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("base_quantity_g", sa.Numeric()),
        sa.Column("ingredient_role", sa.String()),
    )
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(ingredients.insert(), [
            dict(recipe_id=recipe_id, canonical_food_id=food_id, required=required,
                 base_quantity_g=quantity_g,
                 ingredient_role="COOKING_ESSENTIAL" if required else "OPTIONAL")
            for recipe_id, food_id, required, _, quantity_g in INGREDIENTS
        ])
        monkeypatch.setattr(review.op, "get_bind", lambda: connection)
        review.upgrade()
        rows = connection.execute(sa.select(ingredients)).mappings().all()
        assert sum(not row["required"] for row in rows) == 40
        assert all(row["base_quantity_g"] > 0 and row["ingredient_role"] == "COOKING_ESSENTIAL"
                   for row in rows if row["required"] and row["canonical_food_id"] in review.ESSENTIAL_BASE_G)
        review.downgrade()
        rows = connection.execute(sa.select(ingredients)).mappings().all()
        assert sum(not row["required"] for row in rows) == 125
        assert all(row["base_quantity_g"] is None for row in rows if not row["required"])


def test_full_post_v4_optionality_review_and_exact_rollback(monkeypatch):
    """The serving catalogue has 145 optional rows, not the seed's 125."""
    engine = sa.create_engine("sqlite:///:memory:")
    metadata = sa.MetaData()
    ingredients = sa.Table(
        "recipe_catalog_ingredient", metadata,
        sa.Column("recipe_id", sa.String(), nullable=False),
        sa.Column("canonical_food_id", sa.String(), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("base_quantity_g", sa.Numeric()),
        sa.Column("ingredient_role", sa.String()),
    )
    metadata.create_all(engine)
    legacy_pairs = set(SEASONING_ROWS)
    restored = {(r, f) for r, f, _ in legacy_review.REVIEWED_ESSENTIALS}
    assert len(legacy_pairs) == 20 and len(restored) == 15 and restored <= legacy_pairs
    assert legacy_pairs - restored == {
        ("garlic-long-beans", "SF058"), ("sardine-sambal-with-rice", "SF098"),
        ("soy-sauce-eggs-with-rice", "SF118"), ("soy-sauce-mackerel-with-rice", "SF118"),
        ("tomato-tofu-with-rice", "SF118"),
    }
    with engine.begin() as connection:
        connection.execute(ingredients.insert(), [
            dict(recipe_id=r, canonical_food_id=f,
                 required=req and (r, f) not in legacy_pairs, base_quantity_g=q,
                 ingredient_role="SEASONING" if (r, f) in legacy_pairs else
                 ("COOKING_ESSENTIAL" if req else "OPTIONAL"))
            for r, f, req, _, q in INGREDIENTS
        ])
        select = sa.select(ingredients).order_by(ingredients.c.recipe_id, ingredients.c.canonical_food_id)
        before = connection.execute(select).mappings().all()
        assert sum(not row["required"] for row in before) == 145
        monkeypatch.setattr(review.op, "get_bind", lambda: connection)
        review.upgrade()
        legacy_review.upgrade()
        after = connection.execute(select).mappings().all()
        assert sum(not row["required"] for row in after) == 45
        assert sum(a != b for a, b in zip(before, after)) == 100
        assert all(row["required"] and row["ingredient_role"] == "COOKING_ESSENTIAL"
                   for row in after if (row["recipe_id"], row["canonical_food_id"]) in restored)
        # Reapplying does not change rows; no broad seasoning updates.
        review.upgrade()
        legacy_review.upgrade()
        assert connection.execute(select).mappings().all() == after
        legacy_review.downgrade()
        review.downgrade()
        assert connection.execute(select).mappings().all() == before


def test_promoted_essentials_link_to_reviewed_existing_steps():
    from migrations.versions.h4b5c6d7e8f9_link_reviewed_recipe_essentials import STEP_FOODS
    from migrations.versions.p3q4r5s6t7u8_seed_epic5_35_recipe_collection import STEPS
    promoted = {(r, f) for f, recipes in review.PROMOTION_RECIPE_IDS.items() for r in recipes}
    promoted |= {(r, f) for r, f, _ in legacy_review.REVIEWED_ESSENTIALS}
    links = [(r, s, f) for r, s, foods in STEP_FOODS for f in foods.split()]
    assert len(links) == len(set(links)) == 100
    assert {(r, f) for r, _, f in links} == promoted
    assert {(r, s) for r, s, _ in links} <= {(r, s) for r, s, _ in STEPS}
    # Oil is used for frying, not dhal simmering or chicken marination.
    assert ("dhal-curry-with-rice", 3, "SF120") in links
    assert ("tomato-chicken-with-rice", 2, "SF120") in links
    assert ("tomato-chicken-with-rice", 1, "SF135") in links
