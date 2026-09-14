"""
Phase 1 sanity test: the API boots and responds.

We use httpx's ASGITransport to call the FastAPI app in-process — no real
server or network socket needed, which makes this test fast and CI-friendly.
"""
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_root_endpoint() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert response.json()["message"] == "CareerForge AI API"


@pytest.mark.asyncio
async def test_health_endpoint_reports_database_status() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] in ("ok", "unreachable")
