from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from services.api.app.db import AppUser, AuthSession
from services.api.app.main import _issue_tokens, register
from services.api.app.schemas import AuthRegisterRequest


class FakeAsyncSession:
    def __init__(self, *, fail_flush: bool = False, fail_on_session_add: bool = False) -> None:
        self.fail_flush = fail_flush
        self.fail_on_session_add = fail_on_session_add
        self.added: list[object] = []
        self.commits = 0
        self.flushes = 0
        self.rollbacks = 0

    def add(self, entity: object) -> None:
        if self.fail_on_session_add and isinstance(entity, AuthSession):
            raise RuntimeError("session insert failed")
        self.added.append(entity)

    async def flush(self) -> None:
        self.flushes += 1
        if self.fail_flush:
            raise IntegrityError("insert into app_user", {}, Exception("duplicate key"))
        for entity in self.added:
            if isinstance(entity, AppUser) and entity.user_id is None:
                entity.user_id = uuid.uuid4()

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


@pytest.mark.asyncio
async def test_issue_tokens_can_defer_commit() -> None:
    db = FakeAsyncSession()
    user = AppUser(
        user_id=uuid.uuid4(),
        email="user@example.com",
        email_normalized="user@example.com",
        password_hash="hash",
        role="USER",
        status="ACTIVE",
        email_verified=False,
    )

    response = await _issue_tokens(user, db, "MOBILE", commit=False)

    assert response.user.email == "user@example.com"
    assert any(isinstance(entity, AuthSession) for entity in db.added)
    assert db.commits == 0


@pytest.mark.asyncio
async def test_register_commits_user_and_session_together() -> None:
    db = FakeAsyncSession()

    response = await register(
        AuthRegisterRequest(email="new@example.com", password="CorrectHorse123!"),
        db,  # type: ignore[arg-type]
    )

    assert response.user.email == "new@example.com"
    assert [type(entity) for entity in db.added] == [AppUser, AuthSession]
    assert db.flushes == 1
    assert db.commits == 1
    assert db.rollbacks == 0


@pytest.mark.asyncio
async def test_register_duplicate_email_rolls_back_and_returns_409() -> None:
    db = FakeAsyncSession(fail_flush=True)

    with pytest.raises(HTTPException) as exc_info:
        await register(
            AuthRegisterRequest(email="dupe@example.com", password="CorrectHorse123!"),
            db,  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 409
    assert db.commits == 0
    assert db.rollbacks == 1


@pytest.mark.asyncio
async def test_register_rolls_back_if_session_creation_fails() -> None:
    db = FakeAsyncSession(fail_on_session_add=True)

    with pytest.raises(RuntimeError, match="session insert failed"):
        await register(
            AuthRegisterRequest(email="rollback@example.com", password="CorrectHorse123!"),
            db,  # type: ignore[arg-type]
        )

    assert [type(entity) for entity in db.added] == [AppUser]
    assert db.commits == 0
    assert db.rollbacks == 1
