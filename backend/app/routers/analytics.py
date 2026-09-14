# backend/app/routers/analytics.py
"""
Analytics Router — KPI Metrics & Risk Analysis Endpoints (Anil, W4 D4).

Endpoints:
  GET /api/v1/analytics/summary       - KPI Cards summary
  GET /api/v1/analytics/vendors       - Vendor risk matrix
  GET /api/v1/analytics/locations     - Geographic / facility distribution
  GET /api/v1/analytics/trend         - Time-series inspection & fraud trend
  GET /api/v1/analytics/by-operator   - Admin-only per-operator performance breakdown
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.models.user import User, UserRole
from app.schemas.analytics import (
    LocationRiskResponse,
    MonthlyTrendResponse,
    OperatorPerformanceResponse,
    SummaryMetricsResponse,
    VendorRiskResponse,
)
from app.services.analytics_service import analytics_service

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary", response_model=SummaryMetricsResponse)
async def get_summary_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SummaryMetricsResponse:
    """Fetch high-level KPI cards (scoped to user if operator)."""
    return await analytics_service.get_summary_metrics(db, current_user)


@router.get("/vendors", response_model=VendorRiskResponse)
@router.get("/vendor-risk", response_model=VendorRiskResponse, include_in_schema=False)
@router.get("/by-vendor", response_model=VendorRiskResponse, include_in_schema=False)
async def get_vendor_risk(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VendorRiskResponse:
    """Fetch supplier / vendor risk breakdown."""
    return await analytics_service.get_vendor_risk(db, current_user)


@router.get("/locations", response_model=LocationRiskResponse)
@router.get("/by-location", response_model=LocationRiskResponse, include_in_schema=False)
async def get_location_risk(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LocationRiskResponse:
    """Fetch inspection risk distribution by facility / location."""
    return await analytics_service.get_location_risk(db, current_user)


@router.get("/trend", response_model=MonthlyTrendResponse)
@router.get("/monthly-trend", response_model=MonthlyTrendResponse, include_in_schema=False)
async def get_trend(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MonthlyTrendResponse:
    """Fetch monthly time-series trend of inspections and fraud cases."""
    return await analytics_service.get_trend(db, current_user)


@router.get(
    "/by-operator",
    response_model=OperatorPerformanceResponse,
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
async def get_by_operator(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OperatorPerformanceResponse:
    """Admin-only: breakdown of inspection volumes, approvals, and overrides by operator."""
    return await analytics_service.get_operator_performance(db)
