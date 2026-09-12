# backend/tests/test_analytics_and_reports.py
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.main import app
from app.models.inspection import (
    Inspection,
    InspectionStatus,
    InspectionVerdict,
    PolicyAction,
    ReviewDecision,
)
from app.models.user import User, UserRole
from app.models.vendor import Vendor
from app.pipeline.state import inspection_state_registry
from app.services.analytics_service import analytics_service


@pytest.fixture
def admin_user():
    now = datetime.now(timezone.utc)
    return User(
        id=uuid.uuid4(),
        email="admin@visionforge.com",
        full_name="Admin Director",
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
        email="auditor@visionforge.com",
        full_name="Auditor One",
        role=UserRole.OPERATOR,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_analytics_summary_empty(admin_user):
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    res = await analytics_service.get_summary_metrics(mock_db, admin_user)
    assert res.total_inspections == 0
    assert res.fraud_detected_count == 0
    assert res.fraud_rate_pct == 0.0


@pytest.mark.asyncio
async def test_analytics_summary_with_records(admin_user):
    insp1 = Inspection(
        id=uuid.uuid4(),
        case_number="CASE-1",
        vendor_id=uuid.uuid4(),
        location="Site A",
        status=InspectionStatus.COMPLETED,
        verdict=InspectionVerdict.ACCEPT,
        policy_action=PolicyAction.ACCEPT,
        fraud_probability=0.05,
        judge_confidence=0.96,
        created_by=admin_user.id,
    )
    insp2 = Inspection(
        id=uuid.uuid4(),
        case_number="CASE-2",
        vendor_id=uuid.uuid4(),
        location="Site B",
        status=InspectionStatus.COMPLETED,
        verdict=InspectionVerdict.REJECT,
        policy_action=PolicyAction.QUARANTINE,
        fraud_probability=0.88,
        judge_confidence=0.92,
        created_by=admin_user.id,
    )

    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [insp1, insp2]
    mock_db.execute.return_value = mock_result

    res = await analytics_service.get_summary_metrics(mock_db, admin_user)
    assert res.total_inspections == 2
    assert res.fraud_detected_count == 1
    assert res.accepted_count == 1
    assert res.quarantined_count == 1
    assert res.fraud_rate_pct == 50.0


@pytest.mark.asyncio
async def test_analytics_by_operator_rbac_forbidden_for_operator(operator_user):
    mock_db = AsyncMock(spec=AsyncSession)
    app.dependency_overrides[get_current_user] = lambda: operator_user
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/analytics/by-operator")
            assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_analytics_by_operator_allowed_for_admin(admin_user):
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.all.return_value = [
        (admin_user.id, admin_user.full_name, admin_user.email, uuid.uuid4(), ReviewDecision.APPROVED)
    ]
    mock_db.execute.return_value = mock_result

    app.dependency_overrides[get_current_user] = lambda: admin_user
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/analytics/by-operator")
            assert resp.status_code == 200
            data = resp.json()
            assert "items" in data
            assert len(data["items"]) == 1
            assert data["items"][0]["approved_count"] == 1
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_reports_list_endpoint(admin_user):
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    app.dependency_overrides[get_current_user] = lambda: admin_user
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/reports")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 0
            assert data["items"] == []
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_inspection_status_polling_from_registry(admin_user):
    insp_id = uuid.uuid4()
    state = await inspection_state_registry.get_or_create(insp_id)
    app.dependency_overrides[get_current_user] = lambda: admin_user

    try:
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/api/v1/inspections/{insp_id}/status")
            assert resp.status_code == 200
            data = resp.json()
            assert "stage" in data
            assert "stage_name" in data
            assert "status" in data
    finally:
        await inspection_state_registry.release(insp_id)
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_inspection_events_sse_stream(admin_user):
    insp_id = uuid.uuid4()
    state = await inspection_state_registry.get_or_create(insp_id)
    # Set memory to finished status so SSE stream closes immediately
    from app.shared.memory import PipelineStageName, StageResult
    await state.record_stage(
        StageResult(
            stage=PipelineStageName.POLICY_ENGINE,
            status="passed",
            data={"policy_action": "accept"},
        )
    )

    mock_db = AsyncMock(spec=AsyncSession)
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            async with client.stream("GET", f"/api/v1/inspections/{insp_id}/events") as response:
                assert response.status_code == 200
                assert "text/event-stream" in response.headers.get("content-type", "")
                chunks = []
                async for chunk in response.aiter_text():
                    chunks.append(chunk)
                    if "verdict" in chunk:
                        break
                assert len(chunks) > 0
    finally:
        await inspection_state_registry.release(insp_id)
        app.dependency_overrides.clear()
