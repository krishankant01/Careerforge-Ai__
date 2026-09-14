"""
Shared test fixtures.

Phase 1's test_health.py talks to the app's real (Postgres) engine and just
tolerates a "database: unreachable" result. Auth and resume tests need to
actually read/write rows, so here we override get_db with an in-memory
async SQLite session instead — fast, isolated per test, and needs no
running Postgres.

Phase 3 adds a wrinkle: resume_service.process_resume_upload runs as a
FastAPI BackgroundTask and opens its OWN session via
`app.core.database.AsyncSessionLocal`, independent of the request's
session. For that background work to be visible to assertions made via the
API, its session factory must point at the exact same in-memory engine as
the request-scoped session — so `client` also monkeypatches
`database.AsyncSessionLocal` for the duration of the test. StaticPool is
required for this to work: SQLite's `:memory:` database is normally
per-connection, so without forcing a single shared connection, the
request session and the background task's session would each see an
empty, unrelated database.
"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core import database
from app.core.database import get_db
from app.main import app
from app.models import Base

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def test_engine():
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    session_factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session: AsyncSession, test_engine, monkeypatch):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # See module docstring: point the background task's session factory at
    # the same test engine the request session uses.
    background_session_factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    monkeypatch.setattr(database, "AsyncSessionLocal", background_session_factory)

    # Disable rate limiting for tests to prevent 429 errors when multiple tests register users
    from app.core.rate_limit import limiter
    monkeypatch.setattr(limiter, "enabled", False)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient) -> dict:
    """Registers a fresh user and returns headers with a valid Bearer token."""
    resp = await client.post(
        "/api/auth/register",
        json={"name": "Test User", "email": "resumetester@example.com", "password": "password1"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
