"""Per-account profile API (GET/PUT /api/v1/profile) contracts."""
from __future__ import annotations

import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from services.api.app.db import AppUser, AsyncSessionLocal, engine
from services.api.app.main import app

client = TestClient(app)

RUN = uuid.uuid4().hex[:8].lower()
EMAIL = f"profile-{RUN}@example.com"


def _run_db(coro):
    async def runner():
        try:
            return await coro
        finally:
            await engine.dispose()

    return asyncio.run(runner())


@pytest.fixture(scope="module", autouse=True)
def _leave_no_test_data():
    yield

    async def _cleanup():
        async with AsyncSessionLocal() as db:
            user = (
                await db.execute(select(AppUser).where(AppUser.email_normalized == EMAIL))
            ).scalar_one_or_none()
            if user is not None:
                await db.execute(delete(AppUser).where(AppUser.user_id == user.user_id))
            await db.commit()

    _run_db(_cleanup())


@pytest.fixture(scope="module")
def token() -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": EMAIL, "password": "CorrectHorse123!"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_profile_requires_auth():
    assert client.get("/api/v1/profile").status_code == 401
    assert client.put("/api/v1/profile", json={"profile": {}}).status_code == 401


def test_profile_roundtrip(token):
    headers = {"Authorization": f"Bearer {token}"}

    # Fresh account: nothing stored yet
    assert client.get("/api/v1/profile", headers=headers).json() == {"profile": None}

    profile = {
        "version": 1,
        "adults": 2,
        "children": 1,
        "weeklyBudget": 220,
        "state": "Selangor",
        "district": "Petaling",
        "usualBasket": {"staples": ["SF001"], "protein": ["SF003"]},
    }
    saved = client.put("/api/v1/profile", headers=headers, json={"profile": profile})
    assert saved.status_code == 200, saved.text

    loaded = client.get("/api/v1/profile", headers=headers).json()["profile"]
    assert loaded == profile

    # Update replaces wholesale; clearing stores null again
    client.put("/api/v1/profile", headers=headers, json={"profile": None})
    assert client.get("/api/v1/profile", headers=headers).json() == {"profile": None}


def test_profile_rejects_non_object(token):
    headers = {"Authorization": f"Bearer {token}"}
    bad = client.put("/api/v1/profile", headers=headers, json={"profile": [1, 2, 3]})
    assert bad.status_code == 422
