"""
Async SQLAlchemy engine, session management, connection pooling.
Alembic reads Base + DATABASE_URL from here.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


def _build_engine() -> AsyncEngine | None:
    is_test = settings.ENVIRONMENT == "test"
    db_url = settings.DATABASE_URL

    if is_test or "sqlite" in db_url:
        try:
            return create_async_engine(
                db_url if "sqlite" in db_url else "sqlite+aiosqlite:///:memory:",
                echo=settings.DATABASE_ECHO,
                future=True,
                poolclass=NullPool,
            )
        except Exception:
            pass

    try:
        return create_async_engine(
            db_url,
            echo=settings.DATABASE_ECHO,
            future=True,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_timeout=settings.DB_POOL_TIMEOUT,
            pool_recycle=settings.DB_POOL_RECYCLE,
            pool_pre_ping=True,
        )
    except Exception as e:
        logger.warning(
            "Primary database engine init deferred or driver missing: %s", e
        )
        try:
            return create_async_engine(
                "sqlite+aiosqlite:///:memory:",
                future=True,
                poolclass=NullPool,
            )
        except Exception:
            logger.warning("No async DB driver (asyncpg/aiosqlite) found. Engine will be None until driver is installed.")
            return None


engine: AsyncEngine | None = _build_engine()

AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = (
    async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    if engine is not None
    else None
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency. Yields session, commits on success, rolls back on error."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("DB session rolled back due to exception")
            raise
        finally:
            await session.close()


@asynccontextmanager
async def db_session_ctx() -> AsyncGenerator[AsyncSession, None]:
    """Use outside FastAPI DI — pipeline stages, background tasks, scripts."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("DB session (ctx manager) rolled back due to exception")
            raise
        finally:
            await session.close()


async def check_db_connection() -> bool:
    """Health-check helper for /health endpoint."""
    from sqlalchemy import text

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.exception("DB health check failed")
        return False


async def init_db() -> None:
    """Create tables directly — dev/test convenience only. Prod uses Alembic migrations."""
    import app.models  # noqa: F401  ensure model metadata registered

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def dispose_engine() -> None:
    """Call on app shutdown to close pool connections cleanly."""
    await engine.dispose()