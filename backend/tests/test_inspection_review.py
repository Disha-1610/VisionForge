# backend/tests/test_inspection_review.py
"""
Human-review flow regression tests.

The console posts to ``/inspections/{id}/review``, which previously had no route
at all and answered 404. These tests lock down the contract the console relies
on: approve, override-with-verdict-change, and the rejection paths.
"""
from __future__ import annotations

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
    ReviewDecision,
)
from app.models.user import User, UserRole


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


def make_completed_inspection(verdict=InspectionVerdict.REVIEW) -> Inspection:
    now = datetime.now(timezone.utc)
    return Inspection(
        id=uuid.uuid4(),
        case_number="VF-TEST-0001",
        vendor_id=uuid.uuid4(),
        location="Line A",
        image_paths=["uploads/a.png"],
        image_count=1,
        status=InspectionStatus.COMPLETED,
        verdict=verdict,
        review_decision=ReviewDecision.PENDING,
        quality_passed=True,
        authenticity_flagged=False,
        created_by=uuid.uuid4(),
        created_at=now,
        updated_at=now,
    )


def make_db(inspection: Inspection | None) -> AsyncMock:
    """Mock session whose SELECT resolves to `inspection`."""
    mock_db = AsyncMock(spec=AsyncSession)
    result = MagicMock()
    result.scalar_one_or_none.return_value = inspection
    mock_db.execute.return_value = result
    return mock_db


async def post_review(inspection, operator_user, payload):
    mock_db = make_db(inspection)
    app.dependency_overrides[get_current_user] = lambda: operator_user
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                f"/api/v1/inspections/{inspection.id}/review", json=payload
            )
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_review_approve_uses_console_field_names(operator_user):
    """The console sends review_status/reviewer_notes, not the canonical names."""
    inspection = make_completed_inspection()
    resp = await post_review(
        inspection, operator_user, {"review_status": "APPROVED", "reviewer_notes": "Matches golden"}
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["review_decision"] == "approved"
    assert data["reviewer_comment"] == "Matches golden"
    assert data["reviewed_at"] is not None
    # Approval must not mutate the AI verdict.
    assert data["verdict"] == "review"
    assert inspection.reviewed_by == operator_user.id


@pytest.mark.asyncio
async def test_review_override_applies_new_verdict(operator_user):
    inspection = make_completed_inspection(verdict=InspectionVerdict.ACCEPT)
    resp = await post_review(
        inspection,
        operator_user,
        {
            "review_status": "OVERRIDDEN",
            "reviewer_notes": "Seal visibly broken",
            "overridden_verdict": "reject",
        },
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["review_decision"] == "overridden"
    assert data["verdict"] == "reject"
    assert inspection.verdict is InspectionVerdict.REJECT


@pytest.mark.asyncio
async def test_review_accepts_canonical_field_names(operator_user):
    inspection = make_completed_inspection()
    resp = await post_review(
        inspection, operator_user, {"review_decision": "approved", "reviewer_comment": "ok"}
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["reviewer_comment"] == "ok"


@pytest.mark.asyncio
async def test_review_override_requires_comment(operator_user):
    inspection = make_completed_inspection()
    resp = await post_review(
        inspection,
        operator_user,
        {"review_status": "OVERRIDDEN", "reviewer_notes": "  ", "overridden_verdict": "reject"},
    )

    assert resp.status_code == 400
    assert "comment" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_review_override_requires_verdict(operator_user):
    inspection = make_completed_inspection()
    resp = await post_review(
        inspection, operator_user, {"review_status": "OVERRIDDEN", "reviewer_notes": "changed my mind"}
    )

    assert resp.status_code == 400
    assert "overridden_verdict" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_review_rejects_unknown_decision(operator_user):
    inspection = make_completed_inspection()
    resp = await post_review(inspection, operator_user, {"review_status": "sideways"})

    assert resp.status_code == 400
    assert "review_decision" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_review_requires_completed_inspection(operator_user):
    inspection = make_completed_inspection()
    inspection.status = InspectionStatus.PROCESSING
    resp = await post_review(inspection, operator_user, {"review_status": "APPROVED"})

    assert resp.status_code == 409
    assert "not reviewable" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_review_unknown_inspection_is_404(operator_user):
    inspection = make_completed_inspection()
    mock_db = make_db(None)
    app.dependency_overrides[get_current_user] = lambda: operator_user
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/v1/inspections/{uuid.uuid4()}/review", json={"review_status": "APPROVED"}
            )
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_approve_route_accepts_body(operator_user):
    """/approve previously read payload.comment, which does not exist -> 500."""
    inspection = make_completed_inspection()
    mock_db = make_db(inspection)
    app.dependency_overrides[get_current_user] = lambda: operator_user
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/v1/inspections/{inspection.id}/approve", json={}
            )
        assert resp.status_code == 200, resp.text
        assert resp.json()["review_decision"] == "approved"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_review_against_real_session_eager_loads_display_fields(operator_user):
    """Regression guard for the MissingGreenlet 500.

    ``InspectionResponse.vendor_name`` and ``.product_type`` are Python properties
    over the vendor/golden relationships. Serializing the instance straight after
    ``commit()`` lazy-loads them, which cannot await outside a greenlet context.
    Mocked sessions never expire attributes, so only a real session catches this.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.database import Base
    from app.models.vendor import Vendor

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=True, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    vendor = Vendor(name="Acme Components", site_name="Plant 7", code="ACME")

    async with session_factory() as setup:
        setup.add(vendor)
        await setup.commit()
        await setup.refresh(vendor)

        inspection = Inspection(
            case_number="VF-REAL-0001",
            vendor_id=vendor.id,
            location="Line B",
            image_paths=["uploads/real.png"],
            image_count=1,
            status=InspectionStatus.COMPLETED,
            verdict=InspectionVerdict.ACCEPT,
            review_decision=ReviewDecision.PENDING,
            quality_passed=True,
            authenticity_flagged=False,
            created_by=operator_user.id,
        )
        setup.add(inspection)
        await setup.commit()
        await setup.refresh(inspection)
        inspection_id = inspection.id

    def get_real_session():
        return session_factory()

    app.dependency_overrides[get_current_user] = lambda: operator_user
    app.dependency_overrides[get_db] = get_real_session
    try:
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/v1/inspections/{inspection_id}/review",
                json={
                    "review_status": "OVERRIDDEN",
                    "reviewer_notes": "Seal torn on arrival",
                    "overridden_verdict": "reject",
                },
            )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["review_decision"] == "overridden"
        assert data["verdict"] == "reject"
        # Proves the relationships were eagerly loaded rather than lazy.
        assert data["vendor_name"] == "Acme Components"

        async with session_factory() as verify:
            stored = await verify.get(Inspection, inspection_id)
            assert stored.review_decision is ReviewDecision.OVERRIDDEN
            assert stored.verdict is InspectionVerdict.REJECT
            assert stored.reviewed_by == operator_user.id
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()
