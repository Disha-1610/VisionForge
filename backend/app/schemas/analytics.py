# backend/app/schemas/analytics.py
"""
Analytics Schemas for Dashboard & Executive Reporting (Anil, W4 D4).
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SummaryMetricsResponse(BaseModel):
    total_inspections: int = Field(0, description="Total number of processed inspections")
    fraud_detected_count: int = Field(0, description="Inspections flagged as fraudulent or quarantined")
    fraud_rate_pct: float = Field(0.0, description="Fraud percentage (0-100%)")
    pending_reviews_count: int = Field(0, description="Inspections requiring human review / verification")
    accepted_count: int = Field(0, description="Inspections certified as genuine")
    quarantined_count: int = Field(0, description="Inspections quarantined")
    avg_confidence_pct: float = Field(0.0, description="Average AI confidence score across all inspections")


class VendorRiskItem(BaseModel):
    vendor_id: UUID
    vendor_name: str
    total_inspections: int
    fraud_count: int
    fraud_rate_pct: float
    risk_level: str = Field(..., description="LOW | MEDIUM | HIGH")


class VendorRiskResponse(BaseModel):
    items: list[VendorRiskItem]


class LocationRiskItem(BaseModel):
    location: str
    total_inspections: int
    fraud_count: int
    fraud_rate_pct: float


class LocationRiskResponse(BaseModel):
    items: list[LocationRiskItem]


class MonthlyTrendItem(BaseModel):
    period: str = Field(..., description="Date or month grouping string (e.g. 2026-09)")
    total_inspections: int
    fraud_count: int
    fraud_rate_pct: float


class MonthlyTrendResponse(BaseModel):
    items: list[MonthlyTrendItem]


class OperatorPerformanceItem(BaseModel):
    operator_id: UUID
    operator_name: str
    operator_email: str
    total_inspections: int
    approved_count: int
    overridden_count: int


class OperatorPerformanceResponse(BaseModel):
    items: list[OperatorPerformanceItem]
