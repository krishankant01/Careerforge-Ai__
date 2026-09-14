"""Phase 2 auth tests: register, login, /me, and error shapes."""
import pytest


@pytest.mark.asyncio
async def test_register_success(client) -> None:
    resp = await client.post(
        "/api/auth/register",
        json={"name": "Ada Lovelace", "email": "ada@example.com", "password": "password1"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["email"] == "ada@example.com"
    assert "hashed_password" not in data["user"]


@pytest.mark.asyncio
async def test_register_duplicate_email_rejected(client) -> None:
    payload = {"name": "Ada", "email": "dup@example.com", "password": "password1"}
    first = await client.post("/api/auth/register", json=payload)
    assert first.status_code == 201

    second = await client.post("/api/auth/register", json=payload)
    assert second.status_code == 409
    body = second.json()
    assert body["success"] is False
    assert body["error"]["code"] == "EMAIL_ALREADY_REGISTERED"


@pytest.mark.asyncio
async def test_register_weak_password_rejected(client) -> None:
    resp = await client.post(
        "/api/auth/register",
        json={"name": "Bob", "email": "bob@example.com", "password": "allletters"},
    )
    assert resp.status_code == 422
    assert resp.json()["success"] is False


@pytest.mark.asyncio
async def test_register_invalid_email_rejected(client) -> None:
    resp = await client.post(
        "/api/auth/register",
        json={"name": "Bob", "email": "not-an-email", "password": "password1"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client) -> None:
    await client.post(
        "/api/auth/register",
        json={"name": "Grace Hopper", "email": "grace@example.com", "password": "password1"},
    )
    resp = await client.post(
        "/api/auth/login", json={"email": "grace@example.com", "password": "password1"}
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login_wrong_password_rejected(client) -> None:
    await client.post(
        "/api/auth/register",
        json={"name": "Grace", "email": "grace2@example.com", "password": "password1"},
    )
    resp = await client.post(
        "/api/auth/login", json={"email": "grace2@example.com", "password": "wrongpass1"}
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_login_nonexistent_user_rejected(client) -> None:
    resp = await client.post(
        "/api/auth/login", json={"email": "ghost@example.com", "password": "password1"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_token(client) -> None:
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "NOT_AUTHENTICATED"


@pytest.mark.asyncio
async def test_me_with_invalid_token_rejected(client) -> None:
    resp = await client.get("/api/auth/me", headers={"Authorization": "Bearer garbage.token"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_with_valid_token_succeeds(client) -> None:
    register_resp = await client.post(
        "/api/auth/register",
        json={"name": "Alan Turing", "email": "alan@example.com", "password": "password1"},
    )
    token = register_resp.json()["access_token"]

    resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "alan@example.com"
