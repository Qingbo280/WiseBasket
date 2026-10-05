# Epic 5 pantry quantity normalization contract.

from services.api.app.services.recipe_quantities import (
    PantryQuantity,
    aggregate_available_quantity,
    normalize_pantry_quantity,
    normalize_quantity_to_grams,
)


def test_recipe_quantity_normalizes_kilograms_to_grams():
    # Given a household has 2 kg of chicken.
    quantity = 2
    unit = "kg"

    # When the pantry quantity is normalized for recipe matching.
    available_quantity_g = normalize_quantity_to_grams(quantity=quantity, unit=unit)

    # Then the available quantity is 2000 g.
    assert available_quantity_g == 2000


def test_recipe_quantity_preserves_grams():
    # Given a household has 750 g of chicken.
    quantity = 750
    unit = "g"

    # When the pantry quantity is normalized for recipe matching.
    available_quantity_g = normalize_quantity_to_grams(quantity=quantity, unit=unit)

    # Then the available quantity remains 750 g.
    assert available_quantity_g == 750


def test_recipe_quantity_marks_unsupported_unit_as_unknown():
    # Given a household has one bunch of kangkung without a trusted conversion.
    quantity = 1
    unit = "bunch"

    # When the pantry quantity is normalized for recipe matching.
    result = normalize_pantry_quantity(quantity=quantity, unit=unit)

    # Then its quantity remains unknown and cannot be treated as sufficient.
    assert result.quantity_status == "UNKNOWN"
    assert result.quantity_g is None


def test_recipe_quantity_combines_known_amounts_from_manual_and_receipt_sources():
    # Given chicken is available from manual pantry entry and confirmed receipt.
    quantities = (
        PantryQuantity(quantity_status="KNOWN", quantity_g=500, source="MANUAL"),
        PantryQuantity(quantity_status="KNOWN", quantity_g=1500, source="RECEIPT"),
    )

    # When available chicken is aggregated for recipe matching.
    result = aggregate_available_quantity(quantities=quantities)

    # Then the total is 2000 g and the contributing sources stay identifiable.
    assert result.quantity_status == "KNOWN"
    assert result.quantity_g == 2000
    assert result.sources == ("MANUAL", "RECEIPT")
