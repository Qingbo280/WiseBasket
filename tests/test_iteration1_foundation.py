from datetime import date

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from services.api.app.db import AppUser
from services.api.app.schemas import HouseholdInput
from services.api.app.security import (
    create_access_token,
    hash_password,
    hash_refresh_token,
    require_admin,
    verify_password,
)
from services.api.app.services.store_recommendation import (
    BasketItem,
    LatestPrice,
    StoreLocationCandidate,
    evaluate_store_candidates,
    haversine_km,
)


class _TokenUser:
    user_id = "11111111-1111-1111-1111-111111111111"
    email = "user@example.com"
    role = "USER"


def test_password_is_argon2id_hashed_and_verifiable():
    password_hash = hash_password("correct horse battery staple")
    assert password_hash != "correct horse battery staple"
    assert "$argon2id$" in password_hash
    assert verify_password("correct horse battery staple", password_hash)
    assert not verify_password("wrong password", password_hash)


def test_refresh_token_hash_is_not_plaintext():
    token = "raw-refresh-token-value"
    token_hash = hash_refresh_token(token)
    assert token_hash != token
    assert len(token_hash) == 64


def test_access_token_contains_jwt_shape():
    token = create_access_token(_TokenUser())
    assert token.count(".") == 2


@pytest.mark.asyncio
async def test_rbac_dependency_rejects_user_and_allows_admin():
    user = AppUser(email="u@example.com", email_normalized="u@example.com", password_hash="x", role="USER", status="ACTIVE")
    admin = AppUser(email="a@example.com", email_normalized="a@example.com", password_hash="x", role="ADMIN", status="ACTIVE")

    with pytest.raises(HTTPException) as exc_info:
        await require_admin(user)
    assert exc_info.value.status_code == 403
    assert await require_admin(admin) is admin


@pytest.mark.parametrize(
    "household",
    [
        {"adults": 0, "children": 0},
        {"adults": 2, "children": 1, "household_size": 10},
    ],
)
def test_household_validation_rejects_invalid_member_counts(household):
    with pytest.raises(ValidationError):
        HouseholdInput(**household)


def test_haversine_distance_is_reasonable_for_kl_to_pj():
    distance = haversine_km(3.1390, 101.6869, 3.1073, 101.6067)
    assert 8.0 < distance < 10.0


def test_store_evaluator_selects_one_best_value_store_without_inventing_prices():
    stores = [
        StoreLocationCandidate(1, "Near incomplete", 3.1400, 101.6870),
        StoreLocationCandidate(2, "Far complete cheaper", 3.1000, 101.6000),
    ]
    basket = [BasketItem("SF001", 1000), BasketItem("SF002", 500)]
    prices = [
        LatestPrice(101, "SF001", 1, 0.30, date(2026, 8, 20)),
        LatestPrice(201, "SF001", 2, 0.25, date(2026, 8, 21)),
        LatestPrice(202, "SF002", 2, 0.80, date(2026, 8, 21)),
    ]

    evaluations = evaluate_store_candidates(3.1390, 101.6869, stores, basket, prices)

    assert sum(1 for e in evaluations if e.is_selected) == 1
    selected = next(e for e in evaluations if e.is_selected)
    assert selected.location_id == 2
    assert selected.items_available == 2
    assert selected.items_missing == 0

    incomplete = next(e for e in evaluations if e.location_id == 1)
    assert incomplete.items_available == 1
    assert incomplete.items_missing == 1
    assert incomplete.price_coverage_ratio == 0.5
    assert any(not item.available and item.estimated_cost_rm is None for item in incomplete.items)
