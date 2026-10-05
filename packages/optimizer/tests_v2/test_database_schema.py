from services.api.app.db import Base


def test_recipe_catalog_has_v2_governance_columns():
    table = Base.metadata.tables["recipe_catalog"]
    assert {
        "meal_type",
        "recipe_version",
        "review_status",
        "optimizer_eligible",
        "optimizer_component_eligible",
        "quantity_basis",
        "max_weekly_occurrences",
        "reviewed_by",
        "review_source",
        "reviewed_at",
    } <= set(table.columns.keys())


def test_recipe_ingredients_have_explicit_roles():
    table = Base.metadata.tables["recipe_catalog_ingredient"]
    assert "ingredient_role" in table.columns


def test_steps_substitutions_and_safety_use_normalized_tables():
    expected = {
        "recipe_cooking_step_food",
        "recipe_substitution_rule",
        "recipe_substitution_scope",
        "food_safety_profile",
        "food_allergen",
    }
    assert expected <= set(Base.metadata.tables)


def test_substitution_and_safety_foreign_keys_target_canonical_data():
    substitutions = Base.metadata.tables["recipe_substitution_rule"]
    substitution_targets = {
        foreign_key.target_fullname
        for foreign_key in substitutions.foreign_keys
    }
    assert "canonical_food.canonical_food_id" in substitution_targets

    allergens = Base.metadata.tables["food_allergen"]
    allergen_targets = {
        foreign_key.target_fullname
        for foreign_key in allergens.foreign_keys
    }
    assert allergen_targets == {"canonical_food.canonical_food_id"}


def test_food_benefit_tags_use_normalized_evidence_backed_tables():
    assert {"food_tag_definition", "canonical_food_tag"} <= set(Base.metadata.tables)

    definitions = Base.metadata.tables["food_tag_definition"]
    assert {
        "tag_key",
        "display_label",
        "category",
        "icon_key",
        "colour_variant",
        "evidence_source",
        "display_priority",
        "is_active",
    } <= set(definitions.columns.keys())

    assignments = Base.metadata.tables["canonical_food_tag"]
    assert {
        "canonical_food_id",
        "tag_key",
        "source_nutrition_id",
        "nutrient_key",
        "nutrient_value",
        "qualifying_threshold",
        "nutrient_unit",
        "display_priority",
    } <= set(assignments.columns.keys())
    assert {
        foreign_key.target_fullname for foreign_key in assignments.foreign_keys
    } == {
        "canonical_food.canonical_food_id",
        "food_nutrition.nutrition_id",
        "food_tag_definition.tag_key",
    }
