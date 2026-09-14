"""
Health check endpoint.

Purpose: prove the API is up AND that it can reach the database. A "health"
endpoint that only checks the former gives false confidence in production
(e.g. a container is "running" but its DB connection is broken).
"""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)) -> dict:
    db_status = "ok"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unreachable"

    return {
        "status": "ok",
        "database": db_status,
    }
