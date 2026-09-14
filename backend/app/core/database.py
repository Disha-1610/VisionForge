"""
Async SQLAlchemy engine, session management, connection pooling.
Alembic reads Base + DATABASE_URL from here.
"""
from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from datetime import date, datetime
from enum import Enum
from typing import Any, AsyncGenerator
from uuid import UUID

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


def _custom_json_serializer(obj: Any) -> str:
    """Safe JSON serializer for SQLite and PostgreSQL JSON columns handling UUIDs, dates, and enums."""
    def _default(o: Any) -> Any:
        if isinstance(o, UUID):
            return str(o)
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        if isinstance(o, Enum):
            return o.value
        if hasattr(o, "item"):  # numpy scalar types
            return o.item()
        if hasattr(o, "tolist"):  # numpy arrays
            return o.tolist()
        return str(o)

    return json.dumps(obj, default=_default)


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
                json_serializer=_custom_json_serializer,
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
            json_serializer=_custom_json_serializer,
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
                json_serializer=_custom_json_serializer,
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
    """Create tables directly and seed default demo users and vendors if missing."""
    import app.models  # noqa: F401  ensure model metadata registered
    from app.models.user import User, UserRole
    from app.models.vendor import Vendor
    from app.core.security import hash_password
    from sqlalchemy import select

    if engine is None:
        return

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed demo users and vendors
    if AsyncSessionLocal is not None:
        async with AsyncSessionLocal() as session:
            # Check if users exist
            result = await session.execute(select(User).limit(1))
            if result.scalar_one_or_none() is None:
                admin = User(
                    email="admin@visionforge.ai",
                    hashed_password=hash_password("adminpassword123"),
                    full_name="VisionForge Admin",
                    role=UserRole.ADMIN,
                    is_active=True,
                )
                operator = User(
                    email="operator@visionforge.ai",
                    hashed_password=hash_password("operatorpassword123"),
                    full_name="Line Operator",
                    role=UserRole.OPERATOR,
                    is_active=True,
                )
                session.add_all([admin, operator])

            # Check if vendors exist
            v_result = await session.execute(select(Vendor).limit(1))
            if v_result.scalar_one_or_none() is None:
                v1 = Vendor(name="Shenzhen MicroTech Ltd.", code="SMT-01", site_name="Shenzhen Plant 4")
                v2 = Vendor(name="Foxconn Industrial Internet", code="FII-04", site_name="Zhengzhou Campus")
                v3 = Vendor(name="Delta Electronics QA", code="DLT-09", site_name="Taoyuan Facility")
                session.add_all([v1, v2, v3])

            await session.commit()


async def dispose_engine() -> None:
    """Call on app shutdown to close pool connections cleanly."""
    await engine.dispose()