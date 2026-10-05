# Epic 5 measured manual-pantry request contract.
import pytest
from pydantic import ValidationError

from services.api.app.schemas import PantryItemCreateRequest, PantryItemUpdateRequest, ReceiptLineConfirmRequest


def test_manual_pantry_create_request_converts_grams_to_kilograms():
    # Given a user enters a measured pantry amount.
    request = PantryItemCreateRequest(canonical_food_id="SF006", quantity=450, unit="g")

    # When the request is validated.
    # Then the public pantry contract normalizes it to kilograms.
    assert request.quantity == 0.45
    assert request.unit == "kg"


def test_manual_pantry_update_request_accepts_a_kilogram_quantity():
    # Given a user corrects a pantry item to a kilogram amount.
    request = PantryItemUpdateRequest(canonical_food_id="SF006", quantity=1.5, unit="kg")

    # When the request is validated.
    # Then it preserves the unit and decimal amount.
    assert request.quantity == 1.5
    assert request.unit == "kg"


def test_receipt_quantity_correction_standardizes_units():
    request = ReceiptLineConfirmRequest(
        line_id="00000000-0000-0000-0000-000000000001",
        canonical_food_id="SF006",
        qty=750,
        unit="ml",
    )

    assert request.qty == 0.75
    assert request.unit == "l"


@pytest.mark.parametrize(
    "payload",
    (
        {"canonical_food_id": "SF006", "quantity": 500},
        {"canonical_food_id": "SF006", "unit": "g"},
        {"canonical_food_id": "SF006", "quantity": 500, "unit": "bunch"},
    ),
)
def test_manual_pantry_quantity_requires_a_supported_complete_pair(payload):
    # Given a manual pantry quantity is incomplete or not weight-based.
    # When the request is validated.
    # Then the API rejects it before it could produce an unsafe stock estimate.
    with pytest.raises(ValidationError):
        PantryItemCreateRequest(**payload)
