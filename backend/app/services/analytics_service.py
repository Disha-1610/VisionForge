# backend/app/services/analytics_service.py
"""
Analytics Service — High Performance KPI & Risk Aggregations (Anil, W4 D4).

Provides database-driven queries for:
- Summary KPI Cards (total, fraud count, fraud rate, pending reviews)
- Vendor Risk Matrix (vendor breakdown, risk categorization)
- Location Distribution (inspections & fraud by audit location)
- Time Series / Trend Analysis (monthly / daily trends)
- Operator Performance Breakdown (auditor inspection counts & review metrics)

Includes strict Role-Based Access Control (RBAC):
- Operators only see their own inspection data (`created_by == user.id`).
- Admins see organization-wide metrics + operator performance.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inspection import (
    Inspection,
    InspectionStatus,
    InspectionVerdict,
    PolicyAction,
    ReviewDecision,
)
from app.models.user import User, UserRole
from app.models.vendor import Vendor
from app.schemas.analytics import (
    LocationRiskItem,
    LocationRiskResponse,
    MonthlyTrendItem,
    MonthlyTrendResponse,
    OperatorPerformanceItem,
    OperatorPerformanceResponse,
    SummaryMetricsResponse,
    VendorRiskItem,
    VendorRiskResponse,
)

logger = logging.getLogger("app.services.analytics_service")


class AnalyticsService:
    """Service providing aggregated inspection analytics with RBAC filtering."""

    def _apply_rbac(self, query, user: User):
        """Filters query to user's own records if operator."""
        if user.role == UserRole.OPERATOR:
            return query.where(Inspection.created_by == user.id)
        return query

    async def get_summary_metrics(self, db: AsyncSession, user: User) -> SummaryMetricsResponse:
        """Calculate high-level summary KPIs."""
        base_query = select(Inspection)
        scoped_query = self._apply_rbac(base_query, user)

        result = await db.execute(scoped_query)
        inspections = result.scalars().all()

        total = len(inspections)
        if total == 0:
            return SummaryMetricsResponse()

        fraud_count = sum(
            1 for i in inspections
            if i.verdict == InspectionVerdict.REJECT
            or (i.policy_action == PolicyAction.QUARANTINE)
            or (i.fraud_probability is not None and i.fraud_probability >= 0.70)
        )
        accepted_count = sum(
            1 for i in inspections
            if i.verdict == InspectionVerdict.ACCEPT or i.policy_action == PolicyAction.ACCEPT
        )
        quarantined_count = sum(
            1 for i in inspections if i.policy_action == PolicyAction.QUARANTINE
        )
        pending_reviews = sum(
            1 for i in inspections
            if i.verdict == InspectionVerdict.REVIEW
            or i.policy_action == PolicyAction.VENDOR_VERIFICATION
            or (i.review_decision == ReviewDecision.PENDING and i.status == InspectionStatus.COMPLETED)
        )

        confidences = [
            i.judge_confidence * 100.0
            for i in inspections
            if i.judge_confidence is not None
        ]
        avg_conf = round(sum(confidences) / len(confidences), 1) if confidences else 95.0
        fraud_rate = round((fraud_count / total) * 100.0, 1)

        return SummaryMetricsResponse(
            total_inspections=total,
            fraud_detected_count=fraud_count,
            fraud_rate_pct=fraud_rate,
            pending_reviews_count=pending_reviews,
            accepted_count=accepted_count,
            quarantined_count=quarantined_count,
            avg_confidence_pct=avg_conf,
        )

    async def get_vendor_risk(self, db: AsyncSession, user: User) -> VendorRiskResponse:
        """Breakdown of inspections and fraud risk by vendor."""
        # Query inspections with vendor join
        query = (
            select(Inspection.vendor_id, Vendor.name, Inspection.verdict, Inspection.policy_action, Inspection.fraud_probability)
            .join(Vendor, Inspection.vendor_id == Vendor.id)
        )
        if user.role == UserRole.OPERATOR:
            query = query.where(Inspection.created_by == user.id)

        result = await db.execute(query)
        rows = result.all()

        vendor_stats: dict[UUID, dict[str, Any]] = {}
        for row in rows:
            v_id, v_name, verdict, policy, fraud_prob = row
            if v_id not in vendor_stats:
                vendor_stats[v_id] = {
                    "vendor_id": v_id,
                    "vendor_name": v_name,
                    "total": 0,
                    "fraud": 0,
                }
            vendor_stats[v_id]["total"] += 1
            is_fraud = (
                verdict == InspectionVerdict.REJECT
                or policy == PolicyAction.QUARANTINE
                or (fraud_prob is not None and fraud_prob >= 0.70)
            )
            if is_fraud:
                vendor_stats[v_id]["fraud"] += 1

        items: list[VendorRiskItem] = []
        for v_id, stats in vendor_stats.items():
            t = stats["total"]
            f = stats["fraud"]
            rate = round((f / t) * 100.0, 1) if t > 0 else 0.0

            if rate >= 20.0 or f >= 3:
                risk_lvl = "HIGH"
            elif rate >= 5.0 or f >= 1:
                risk_lvl = "MEDIUM"
            else:
                risk_lvl = "LOW"

            items.append(
                VendorRiskItem(
                    vendor_id=v_id,
                    vendor_name=stats["vendor_name"],
                    total_inspections=t,
                    fraud_count=f,
                    fraud_rate_pct=rate,
                    risk_level=risk_lvl,
                )
            )

        items.sort(key=lambda x: (x.fraud_rate_pct, x.total_inspections), reverse=True)
        return VendorRiskResponse(items=items)

    async def get_location_risk(self, db: AsyncSession, user: User) -> LocationRiskResponse:
        """Breakdown of inspections and fraud by facility/location."""
        query = select(Inspection.location, Inspection.verdict, Inspection.policy_action, Inspection.fraud_probability)
        if user.role == UserRole.OPERATOR:
            query = query.where(Inspection.created_by == user.id)

        result = await db.execute(query)
        rows = result.all()

        loc_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "fraud": 0})
        for loc, verdict, policy, fraud_prob in rows:
            clean_loc = loc or "Main Facility"
            loc_stats[clean_loc]["total"] += 1
            is_fraud = (
                verdict == InspectionVerdict.REJECT
                or policy == PolicyAction.QUARANTINE
                or (fraud_prob is not None and fraud_prob >= 0.70)
            )
            if is_fraud:
                loc_stats[clean_loc]["fraud"] += 1

        items: list[LocationRiskItem] = []
        for loc, stats in loc_stats.items():
            t = stats["total"]
            f = stats["fraud"]
            rate = round((f / t) * 100.0, 1) if t > 0 else 0.0
            items.append(
                LocationRiskItem(
                    location=loc,
                    total_inspections=t,
                    fraud_count=f,
                    fraud_rate_pct=rate,
                )
            )

        items.sort(key=lambda x: x.total_inspections, reverse=True)
        return LocationRiskResponse(items=items)

    async def get_trend(self, db: AsyncSession, user: User) -> MonthlyTrendResponse:
        """Time series trend of inspections and fraud detections."""
        query = select(Inspection.created_at, Inspection.verdict, Inspection.policy_action, Inspection.fraud_probability)
        if user.role == UserRole.OPERATOR:
            query = query.where(Inspection.created_by == user.id)

        result = await db.execute(query)
        rows = result.all()

        trend_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "fraud": 0})
        for dt, verdict, policy, fraud_prob in rows:
            period = dt.strftime("%Y-%m") if dt else "2026-09"
            trend_stats[period]["total"] += 1
            is_fraud = (
                verdict == InspectionVerdict.REJECT
                or policy == PolicyAction.QUARANTINE
                or (fraud_prob is not None and fraud_prob >= 0.70)
            )
            if is_fraud:
                trend_stats[period]["fraud"] += 1

        items: list[MonthlyTrendItem] = []
        for period in sorted(trend_stats.keys()):
            t = trend_stats[period]["total"]
            f = trend_stats[period]["fraud"]
            rate = round((f / t) * 100.0, 1) if t > 0 else 0.0
            items.append(
                MonthlyTrendItem(
                    period=period,
                    total_inspections=t,
                    fraud_count=f,
                    fraud_rate_pct=rate,
                )
            )

        return MonthlyTrendResponse(items=items)

    async def get_operator_performance(self, db: AsyncSession) -> OperatorPerformanceResponse:
        """Admin-only view: breakdown of inspections, approvals, and overrides per operator."""
        query = (
            select(
                User.id,
                User.full_name,
                User.email,
                Inspection.id,
                Inspection.review_decision,
            )
            .join(Inspection, User.id == Inspection.created_by)
        )
        result = await db.execute(query)
        rows = result.all()

        op_stats: dict[UUID, dict[str, Any]] = {}
        for u_id, full_name, email, insp_id, decision in rows:
            if u_id not in op_stats:
                op_stats[u_id] = {
                    "operator_id": u_id,
                    "operator_name": full_name,
                    "operator_email": email,
                    "total": 0,
                    "approved": 0,
                    "overridden": 0,
                }
            op_stats[u_id]["total"] += 1
            if decision == ReviewDecision.APPROVED:
                op_stats[u_id]["approved"] += 1
            elif decision == ReviewDecision.OVERRIDDEN:
                op_stats[u_id]["overridden"] += 1

        items = [
            OperatorPerformanceItem(
                operator_id=d["operator_id"],
                operator_name=d["operator_name"],
                operator_email=d["operator_email"],
                total_inspections=d["total"],
                approved_count=d["approved"],
                overridden_count=d["overridden"],
            )
            for d in op_stats.values()
        ]
        items.sort(key=lambda x: x.total_inspections, reverse=True)
        return OperatorPerformanceResponse(items=items)


analytics_service = AnalyticsService()
