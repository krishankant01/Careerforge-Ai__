"""
Database connectivity.

We use SQLAlchemy's async engine (via the `asyncpg` driver) because the whole
app is async: FastAPI route handlers are `async def`, and later our AI/GitHub
calls will be too. Mixing sync DB calls into an async app would block the
event loop and quietly kill concurrency.
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,  # logs SQL statements in dev — turn off in prod (see logging)
    pool_pre_ping=True,   # detects stale connections instead of failing requests
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a DB session per request and guarantees
    it's closed afterward, even if the request raises an exception.

    Usage in a route:
        async def some_route(db: AsyncSession = Depends(get_db)): ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
