# backend/tests/test_routers.py
"""
Router integration tests for FastAPI endpoints:
- Health check & root endpoints
- Auth endpoints (me)
- Products endpoints (list)
- Vendors endpoints (dropdown)
- Inspections endpoints (input validation)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.main import app
from app.models.product import GoldenReference
from app.models.user import User, UserRole
from app.models.vendor import Vendor


@pytest.fixture
def admin_user():
    now = datetime.now(timezone.utc)
    return User(
        id=uuid.uuid4(),
        email="admin@test.com",
        full_name="Admin User",
        role=UserRole.ADMIN,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def operator_user():
    now = datetime.now(timezone.utc)
    return User(
        id=uuid.uuid4(),
        email="operator@test.com",
        full_name="Operator User",
        role=UserRole.OPERATOR,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_health_check():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_root_endpoint():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert "VisionForge" in data["name"]


@pytest.mark.asyncio
async def test_auth_me_authenticated(operator_user):
    app.dependency_overrides[get_current_user] = lambda: operator_user
    try:
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/auth/me")
            assert resp.status_code == 200
            assert resp.json()["email"] == "operator@test.com"
            assert resp.json()["role"] == "operator"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_inspections_create_requires_valid_images(operator_user):
    mock_db = AsyncMock(spec=AsyncSession)
    app.dependency_overrides[get_current_user] = lambda: operator_user
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Without images should fail 422 (validation error)
            resp = await client.post(
                "/api/v1/inspections",
                data={"vendor_id": str(uuid.uuid4()), "location": "Site A"},
            )
            assert resp.status_code == 422
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_inspections_list_pagination_validation(operator_user):
    mock_db = AsyncMock(spec=AsyncSession)
    app.dependency_overrides[get_current_user] = lambda: operator_user
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/inspections?page=0")
            assert resp.status_code == 400
            assert "Invalid pagination" in resp.json()["detail"]
    finally:
        app.dependency_overrides.clear()
