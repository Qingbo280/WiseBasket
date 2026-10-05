"""Schema contract for data-driven purchase semantics."""

from services.api.app.db import Base


def test_canonical_food_declares_purchase_mode() -> None:
    table = Base.metadata.tables["canonical_food"]

    assert "purchase_mode" in table.columns
    assert table.columns["purchase_mode"].nullable is False

