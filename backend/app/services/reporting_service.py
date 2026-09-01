"""
backend/app/services/reporting_service.py

Business Service: Reporting.

Responsibility (strict architectural boundary):
    - READ completed pipeline output (authenticity, evidence, judge, policy).
    - RENDER an explainable PDF report via ReportLab.
    - PERSIST + RETRIEVE report metadata.

This service performs NO detection, fusion, judging, or policy logic. All of
that data must already be finalized upstream (pipeline/workflow.py -> Stage 8)
before it reaches `generate_report()`.
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from enum import Enum
from io import BytesIO
from typing import Optional, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image as RLImage,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppException
from app.models.report import Report as ReportORM

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Exceptions
# ─────────────────────────────────────────────


class ReportingServiceError(AppException):
    """Base exception for the reporting service."""

    def __init__(self, message: str, *, status_code: int = 500) -> None:
        super().__init__(message)
        self.status_code = status_code


class ReportGenerationError(ReportingServiceError):
    """Raised when PDF rendering or persistence fails."""

    def __init__(self, message: str) -> None:
        super().__init__(f"Report generation failed: {message}", status_code=500)


class ReportNotFoundError(ReportingServiceError):
    """Raised when a report is requested for an inspection that has none."""

    def __init__(self, inspection_id: uuid.UUID) -> None:
        super().__init__(
            f"No report found for inspection_id={inspection_id}",
            status_code=404,
        )


class ReportValidationError(ReportingServiceError):
    """Raised when the supplied ReportGenerationInput is structurally invalid."""

    def __init__(self, message: str) -> None:
        super().__init__(f"Invalid report input: {message}", status_code=422)


# ─────────────────────────────────────────────
# Domain enums
# ─────────────────────────────────────────────


class Verdict(str, Enum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    REVIEW = "REVIEW"


class RecommendedAction(str, Enum):
    ACCEPT = "ACCEPT"
    RETAKE = "RETAKE"
    QUARANTINE = "QUARANTINE"
    VENDOR_VERIFICATION = "VENDOR_VERIFICATION"


class EvidenceAgent(str, Enum):
    OCR = "OCR"
    LABEL = "LABEL"
    STRUCTURAL = "STRUCTURAL"
    VLM = "VLM"


class EvidenceSeverity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AuthenticityVerdict(str, Enum):
    AUTHENTIC = "AUTHENTIC"
    SUSPICIOUS = "SUSPICIOUS"
    INCONCLUSIVE = "INCONCLUSIVE"


class AnnotationType(str, Enum):
    ROI = "ROI"
    YOLO = "YOLO"


# ─────────────────────────────────────────────
# ROI / image contracts
# ─────────────────────────────────────────────


class BoundingBox(BaseModel):
    model_config = ConfigDict(frozen=True)

    x: float
    y: float
    width: float = Field(gt=0)
    height: float = Field(gt=0)


class ROIReference(BaseModel):
    model_config = ConfigDict(frozen=True)

    roi_id: str = Field(alias="roiId")
    name: str
    type: str
    bounding_box: BoundingBox = Field(alias="boundingBox")
    image_path: str = Field(alias="imagePath")


class Annotation(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: AnnotationType
    label: str
    bounding_box: BoundingBox = Field(alias="boundingBox")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class InspectionImageReference(BaseModel):
    model_config = ConfigDict(frozen=True)

    image_id: uuid.UUID = Field(alias="imageId")
    image_path: str = Field(alias="imagePath")
    angle: Optional[str] = None
    annotations: list[Annotation] = Field(default_factory=list)


# ─────────────────────────────────────────────
# Evidence contract
# ─────────────────────────────────────────────


class EvidenceReportItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_id: uuid.UUID = Field(alias="evidenceId")
    agent: EvidenceAgent
    roi: ROIReference
    finding: str
    explanation: str
    confidence: float = Field(ge=0.0, le=1.0)
    severity: EvidenceSeverity
    processing_time_ms: float = Field(alias="processingTimeMs", ge=0)

    component_class: Optional[str] = Field(default=None, alias="componentClass")
    expected_count: Optional[int] = Field(default=None, alias="expectedCount", ge=0)
    detected_count: Optional[int] = Field(default=None, alias="detectedCount", ge=0)
    missing_count: Optional[int] = Field(default=None, alias="missingCount", ge=0)
    extra_count: Optional[int] = Field(default=None, alias="extraCount", ge=0)

    annotated_image_path: Optional[str] = Field(default=None, alias="annotatedImagePath")
    heatmap_path: Optional[str] = Field(default=None, alias="heatmapPath")


# ─────────────────────────────────────────────
# Judge output
# ─────────────────────────────────────────────


class JudgeResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    verdict: Verdict
    fraud_probability: float = Field(alias="fraudProbability", ge=0.0, le=100.0)
    confidence: float = Field(ge=0.0, le=100.0)
    category: str
    root_cause: str = Field(alias="rootCause")
    explanation: Optional[str] = None
    weighted_evidence_ids: list[uuid.UUID] = Field(
        default_factory=list, alias="weightedEvidenceIds"
    )


# ─────────────────────────────────────────────
# Authenticity output
# ─────────────────────────────────────────────


class AuthenticityResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    score: float = Field(ge=0.0, le=100.0)
    verdict: AuthenticityVerdict
    reasons: list[str] = Field(default_factory=list)


# ─────────────────────────────────────────────
# Policy output
# ─────────────────────────────────────────────


class PolicyResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    fraud_score: float = Field(alias="fraudScore", ge=0.0, le=100.0)
    confidence_score: float = Field(alias="confidenceScore", ge=0.0, le=100.0)
    fraud_category: str = Field(alias="fraudCategory")
    recommended_action: RecommendedAction = Field(alias="recommendedAction")


# ─────────────────────────────────────────────
# Complete reporting input
# ─────────────────────────────────────────────


class ReportGenerationInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    case_id: str = Field(alias="caseId", min_length=1)
    inspection_id: uuid.UUID = Field(alias="inspectionId")

    created_at: datetime = Field(alias="createdAt")
    vendor_name: Optional[str] = Field(default=None, alias="vendorName")
    location: Optional[str] = None
    product_type: Optional[str] = Field(default=None, alias="productType")

    inspection_images: list[InspectionImageReference] = Field(alias="inspectionImages")
    reference_image_path: Optional[str] = Field(default=None, alias="referenceImagePath")

    authenticity: AuthenticityResult
    evidence: list[EvidenceReportItem]
    judge: JudgeResult
    policy: PolicyResult

    @field_validator("inspection_images")
    @classmethod
    def _require_at_least_one_image(
        cls, v: list[InspectionImageReference]
    ) -> list[InspectionImageReference]:
        if not v:
            raise ValueError("inspection_images must contain at least one image")
        return v

    @field_validator("evidence")
    @classmethod
    def _require_at_least_one_evidence_item(
        cls, v: list[EvidenceReportItem]
    ) -> list[EvidenceReportItem]:
        if not v:
            raise ValueError("evidence must contain at least one item")
        return v


# ─────────────────────────────────────────────
# Generated report metadata
# ─────────────────────────────────────────────


class ReportMetadata(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    report_id: uuid.UUID = Field(alias="reportId")
    inspection_id: uuid.UUID = Field(alias="inspectionId")
    case_id: str = Field(alias="caseId")

    generated_at: datetime = Field(alias="generatedAt")

    pdf_path: str = Field(alias="pdfPath")

    verdict: Verdict
    fraud_score: float = Field(alias="fraudScore")
    confidence_score: float = Field(alias="confidenceScore")
    fraud_category: str = Field(alias="fraudCategory")
    recommended_action: RecommendedAction = Field(alias="recommendedAction")


# ─────────────────────────────────────────────
# Service protocol (contract)
# ─────────────────────────────────────────────


class ReportingServiceProtocol(Protocol):
    async def generate_report(self, input: ReportGenerationInput) -> ReportMetadata: ...

    async def get_report(self, inspection_id: uuid.UUID) -> ReportMetadata: ...

    async def get_report_pdf_path(self, inspection_id: uuid.UUID) -> str: ...

    async def report_exists(self, inspection_id: uuid.UUID) -> bool: ...


# ─────────────────────────────────────────────
# Reusable ReportLab styles
# ─────────────────────────────────────────────

_STYLES = getSampleStyleSheet()

_STYLE_TITLE = ParagraphStyle(
    "ReportTitle",
    parent=_STYLES["Title"],
    fontSize=20,
    alignment=TA_CENTER,
    spaceAfter=4,
)

_STYLE_SUBTITLE = ParagraphStyle(
    "ReportSubtitle",
    parent=_STYLES["Normal"],
    fontSize=10,
    alignment=TA_CENTER,
    textColor=colors.HexColor("#64748b"),
    spaceAfter=12,
)

_STYLE_SECTION = ParagraphStyle(
    "SectionHeader",
    parent=_STYLES["Heading2"],
    fontSize=13,
    textColor=colors.HexColor("#0f172a"),
    spaceBefore=14,
    spaceAfter=6,
)

_STYLE_BODY = ParagraphStyle(
    "Body",
    parent=_STYLES["BodyText"],
    fontSize=9.5,
    leading=13,
    alignment=TA_LEFT,
)

_STYLE_CAPTION = ParagraphStyle(
    "Caption",
    parent=_STYLES["Normal"],
    fontSize=8,
    textColor=colors.HexColor("#475569"),
    alignment=TA_CENTER,
)

_VERDICT_COLORS: dict[Verdict, colors.Color] = {
    Verdict.ACCEPT: colors.HexColor("#059669"),
    Verdict.REJECT: colors.HexColor("#dc2626"),
    Verdict.REVIEW: colors.HexColor("#d97706"),
}

_SEVERITY_COLORS: dict[EvidenceSeverity, colors.Color] = {
    EvidenceSeverity.INFO: colors.HexColor("#64748b"),
    EvidenceSeverity.LOW: colors.HexColor("#0ea5e9"),
    EvidenceSeverity.MEDIUM: colors.HexColor("#d97706"),
    EvidenceSeverity.HIGH: colors.HexColor("#ea580c"),
    EvidenceSeverity.CRITICAL: colors.HexColor("#dc2626"),
}


# ─────────────────────────────────────────────
# PDF renderer (pure function — no I/O side effects besides returning bytes)
# ─────────────────────────────────────────────


class _PdfRenderer:
    """Builds the explainable inspection report PDF from finalized pipeline data."""

    PAGE_SIZE = A4
    MARGIN = 18 * mm

    def render(self, data: ReportGenerationInput) -> bytes:
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=self.PAGE_SIZE,
            leftMargin=self.MARGIN,
            rightMargin=self.MARGIN,
            topMargin=self.MARGIN,
            bottomMargin=self.MARGIN,
            title=f"VisionForge Inspection Report — {data.case_id}",
            author="VisionForge AI",
        )

        story: list = []
        story.extend(self._build_header(data))
        story.extend(self._build_summary_table(data))
        story.extend(self._build_authenticity_section(data))
        story.extend(self._build_root_cause_section(data))
        story.append(PageBreak())
        story.extend(self._build_images_section(data))
        story.append(PageBreak())
        story.extend(self._build_evidence_section(data))
        story.extend(self._build_footer(data))

        try:
            doc.build(story)
        except Exception as exc:  # noqa: BLE001 - ReportLab raises assorted errors
            raise ReportGenerationError(f"PDF layout build failed: {exc}") from exc

        return buffer.getvalue()

    # ---- sections -----------------------------------------------------

    def _build_header(self, data: ReportGenerationInput) -> list:
        elements: list = [
            Paragraph("VisionForge AI — Inspection Report", _STYLE_TITLE),
            Paragraph(
                f"Case ID: {data.case_id} &nbsp;|&nbsp; "
                f"Inspection ID: {data.inspection_id} &nbsp;|&nbsp; "
                f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
                _STYLE_SUBTITLE,
            ),
        ]

        verdict_color = _VERDICT_COLORS[data.judge.verdict]
        verdict_table = Table(
            [
                [
                    Paragraph(f"<b>VERDICT: {data.judge.verdict.value}</b>", _STYLE_BODY),
                    Paragraph(
                        f"Fraud Probability: <b>{data.judge.fraud_probability:.1f}%</b>",
                        _STYLE_BODY,
                    ),
                    Paragraph(f"Confidence: <b>{data.judge.confidence:.1f}%</b>", _STYLE_BODY),
                    Paragraph(f"Category: <b>{data.judge.category}</b>", _STYLE_BODY),
                ]
            ],
            colWidths=[110 * mm / 4] * 4 if False else None,
        )
        verdict_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), verdict_color),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.white),
                ]
            )
        )
        elements.append(verdict_table)
        elements.append(Spacer(1, 10))
        return elements

    def _build_summary_table(self, data: ReportGenerationInput) -> list:
        rows = [
            ["Vendor", data.vendor_name or "—", "Location", data.location or "—"],
            [
                "Product Type",
                data.product_type or "—",
                "Recommended Action",
                data.policy.recommended_action.value,
            ],
            [
                "Fraud Score",
                f"{data.policy.fraud_score:.1f}",
                "Confidence Score",
                f"{data.policy.confidence_score:.1f}",
            ],
        ]
        table = Table(rows, colWidths=[35 * mm, 55 * mm, 35 * mm, 55 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f5f9")),
                    ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#f1f5f9")),
                ]
            )
        )
        return [Paragraph("Case Summary", _STYLE_SECTION), table]

    def _build_authenticity_section(self, data: ReportGenerationInput) -> list:
        auth = data.authenticity
        reasons = "; ".join(auth.reasons) if auth.reasons else "No anomalies flagged."
        elements = [
            Paragraph("Image Authenticity", _STYLE_SECTION),
            Paragraph(
                f"<b>Verdict:</b> {auth.verdict.value} &nbsp;&nbsp; "
                f"<b>Score:</b> {auth.score:.1f}/100",
                _STYLE_BODY,
            ),
            Paragraph(f"<b>Reasons:</b> {self._escape(reasons)}", _STYLE_BODY),
        ]
        return elements

    def _build_root_cause_section(self, data: ReportGenerationInput) -> list:
        judge = data.judge
        explanation = judge.explanation or "No supplementary explanation provided."
        return [
            Paragraph("Root Cause Analysis", _STYLE_SECTION),
            Paragraph(f"<b>Root Cause:</b> {self._escape(judge.root_cause)}", _STYLE_BODY),
            Paragraph(f"<b>Judge Explanation:</b> {self._escape(explanation)}", _STYLE_BODY),
            Paragraph(
                f"<b>Evidence Items Weighted in Decision:</b> {len(judge.weighted_evidence_ids)}",
                _STYLE_BODY,
            ),
        ]

    def _build_images_section(self, data: ReportGenerationInput) -> list:
        elements: list = [Paragraph("Inspection Images & ROI Overlays", _STYLE_SECTION)]

        if data.reference_image_path:
            elements.extend(self._image_block("Golden Reference", data.reference_image_path))

        for img in data.inspection_images:
            label = f"Inspection Image ({img.angle})" if img.angle else "Inspection Image"
            annotation_summary = self._summarize_annotations(img.annotations)
            elements.extend(
                self._image_block(label, img.image_path, caption=annotation_summary)
            )

        return elements

    def _summarize_annotations(self, annotations: list[Annotation]) -> Optional[str]:
        if not annotations:
            return None
        roi_count = sum(1 for a in annotations if a.type == AnnotationType.ROI)
        yolo_count = sum(1 for a in annotations if a.type == AnnotationType.YOLO)
        parts = []
        if roi_count:
            parts.append(f"{roi_count} ROI region(s)")
        if yolo_count:
            parts.append(f"{yolo_count} YOLO detection(s)")
        return ", ".join(parts) if parts else None

    def _image_block(self, label: str, path: str, caption: Optional[str] = None) -> list:
        elements: list = [Paragraph(f"<b>{self._escape(label)}</b>", _STYLE_BODY)]
        img_flowable = self._safe_image(path)
        if img_flowable is not None:
            elements.append(img_flowable)
        else:
            elements.append(
                Paragraph(
                    f"<i>Image unavailable at path: {self._escape(path)}</i>", _STYLE_CAPTION
                )
            )
        if caption:
            elements.append(Paragraph(self._escape(caption), _STYLE_CAPTION))
        elements.append(Spacer(1, 8))
        return elements

    def _safe_image(self, path: str, max_width_mm: float = 150.0) -> Optional[RLImage]:
        if not path or not os.path.isfile(path):
            logger.warning("reporting_service: image not found on disk: %s", path)
            return None
        try:
            img = RLImage(path)
            max_w = max_width_mm * mm
            if img.drawWidth > max_w:
                scale = max_w / img.drawWidth
                img.drawWidth *= scale
                img.drawHeight *= scale
            return img
        except Exception as exc:  # noqa: BLE001 - Pillow/ReportLab raise assorted errors
            logger.warning("reporting_service: failed to load image %s: %s", path, exc)
            return None

    def _build_evidence_section(self, data: ReportGenerationInput) -> list:
        elements: list = [Paragraph("Evidence — Per Agent Findings", _STYLE_SECTION)]

        by_agent: dict[EvidenceAgent, list[EvidenceReportItem]] = {}
        for item in data.evidence:
            by_agent.setdefault(item.agent, []).append(item)

        for agent in EvidenceAgent:
            items = by_agent.get(agent)
            if not items:
                continue
            elements.append(Paragraph(f"{agent.value} Agent", _STYLE_SECTION))
            for item in items:
                elements.append(KeepTogether(self._evidence_card(item)))

        return elements

    def _evidence_card(self, item: EvidenceReportItem) -> list:
        severity_color = _SEVERITY_COLORS[item.severity]
        header_row = [
            Paragraph(f"<b>{self._escape(item.roi.name)}</b> ({item.roi.type})", _STYLE_BODY),
            Paragraph(
                f"<font color='{severity_color.hexval()}'><b>{item.severity.value}</b></font>",
                _STYLE_BODY,
            ),
            Paragraph(f"Confidence: {item.confidence * 100:.1f}%", _STYLE_BODY),
        ]

        rows = [header_row]
        rows.append([Paragraph(f"<b>Finding:</b> {self._escape(item.finding)}", _STYLE_BODY), "", ""])
        rows.append(
            [Paragraph(f"<b>Explanation:</b> {self._escape(item.explanation)}", _STYLE_BODY), "", ""]
        )

        if item.component_class is not None or item.expected_count is not None:
            count_line = (
                f"<b>Component:</b> {self._escape(item.component_class or '—')} &nbsp;&nbsp; "
                f"<b>Expected:</b> {item.expected_count if item.expected_count is not None else '—'} "
                f"&nbsp;&nbsp; <b>Detected:</b> "
                f"{item.detected_count if item.detected_count is not None else '—'} "
                f"&nbsp;&nbsp; <b>Missing:</b> "
                f"{item.missing_count if item.missing_count is not None else 0} "
                f"&nbsp;&nbsp; <b>Extra:</b> {item.extra_count if item.extra_count is not None else 0}"
            )
            rows.append([Paragraph(count_line, _STYLE_BODY), "", ""])

        rows.append(
            [
                Paragraph(
                    f"<font size=8 color='#64748b'>Processing time: "
                    f"{item.processing_time_ms:.0f} ms &nbsp;|&nbsp; Evidence ID: {item.evidence_id}</font>",
                    _STYLE_CAPTION,
                ),
                "",
                "",
            ]
        )

        table = Table(rows, colWidths=[110 * mm, 30 * mm, 30 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("SPAN", (0, 1), (-1, 1)),
                    ("SPAN", (0, 2), (-1, 2)),
                    ("SPAN", (0, 3), (-1, 3)) if len(rows) > 4 else ("SPAN", (0, 3), (-1, 3)),
                    ("SPAN", (0, len(rows) - 1), (-1, len(rows) - 1)),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8fafc")),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        return [table, Spacer(1, 6)]

    def _build_footer(self, data: ReportGenerationInput) -> list:
        return [
            Spacer(1, 14),
            Paragraph(
                "Generated automatically by VisionForge AI. This report reflects the "
                "output of the AI Judge and Policy Engine; recommended actions require "
                "human Approve/Override per the platform's review workflow.",
                _STYLE_CAPTION,
            ),
        ]

    @staticmethod
    def _escape(text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )


# ─────────────────────────────────────────────
# Reporting service implementation
# ─────────────────────────────────────────────


class ReportingService:
    """
    Concrete ReportingService.

    Persists report metadata via SQLAlchemy (async) and writes rendered PDFs
    to disk under `settings.REPORTS_DIR`. All blocking work (ReportLab layout,
    file I/O) is offloaded to a worker thread via `asyncio.to_thread` so the
    event loop is never blocked.
    """

    def __init__(self, session: AsyncSession, reports_dir: Optional[str] = None) -> None:
        self._session = session
        self._renderer = _PdfRenderer()
        self._reports_dir = reports_dir or getattr(settings, "REPORTS_DIR", "data/reports")
        os.makedirs(self._reports_dir, exist_ok=True)

    # ---- public contract -----------------------------------------------

    async def generate_report(self, input: ReportGenerationInput) -> ReportMetadata:
        """
        Render and persist the explainable PDF report for a completed inspection.
        Idempotent: re-generating for the same inspection_id overwrites the
        existing PDF and updates the existing metadata row (reproducibility).
        """
        try:
            pdf_bytes = await asyncio.to_thread(self._renderer.render, input)
        except ReportGenerationError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "reporting_service: unexpected error rendering PDF for inspection_id=%s",
                input.inspection_id,
            )
            raise ReportGenerationError(str(exc)) from exc

        pdf_path = self._resolve_pdf_path(input.inspection_id, input.case_id)

        try:
            await asyncio.to_thread(self._write_pdf_atomic, pdf_path, pdf_bytes)
        except OSError as exc:
            logger.exception(
                "reporting_service: failed writing PDF to disk for inspection_id=%s",
                input.inspection_id,
            )
            raise ReportGenerationError(f"failed to write PDF file: {exc}") from exc

        try:
            report_row = await self._upsert_report_row(input, pdf_path)
        except SQLAlchemyError as exc:
            logger.exception(
                "reporting_service: failed persisting report metadata for inspection_id=%s",
                input.inspection_id,
            )
            await self._session.rollback()
            raise ReportGenerationError(f"failed to persist report metadata: {exc}") from exc

        logger.info(
            "reporting_service: report generated inspection_id=%s report_id=%s pdf_path=%s",
            input.inspection_id,
            report_row.id,
            pdf_path,
        )

        return self._to_metadata(report_row)

    async def get_report(self, inspection_id: uuid.UUID) -> ReportMetadata:
        report_row = await self._fetch_report_row(inspection_id)
        if report_row is None:
            raise ReportNotFoundError(inspection_id)
        return self._to_metadata(report_row)

    async def get_report_pdf_path(self, inspection_id: uuid.UUID) -> str:
        report_row = await self._fetch_report_row(inspection_id)
        if report_row is None:
            raise ReportNotFoundError(inspection_id)
        if not os.path.isfile(report_row.pdf_path):
            logger.error(
                "reporting_service: PDF file missing on disk for inspection_id=%s path=%s",
                inspection_id,
                report_row.pdf_path,
            )
            raise ReportingServiceError(
                f"Report PDF file missing on disk for inspection_id={inspection_id}",
                status_code=410,
            )
        return report_row.pdf_path

    async def report_exists(self, inspection_id: uuid.UUID) -> bool:
        report_row = await self._fetch_report_row(inspection_id)
        return report_row is not None

    # ---- internals -------------------------------------------------------

    def _resolve_pdf_path(self, inspection_id: uuid.UUID, case_id: str) -> str:
        safe_case_id = "".join(
            c if (c.isalnum() or c in ("-", "_")) else "_" for c in case_id
        ) or "case"
        filename = f"{safe_case_id}_{inspection_id}.pdf"
        return os.path.join(self._reports_dir, filename)

    @staticmethod
    def _write_pdf_atomic(path: str, content: bytes) -> None:
        tmp_path = f"{path}.tmp-{uuid.uuid4().hex}"
        try:
            with open(tmp_path, "wb") as fh:
                fh.write(content)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_path, path)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    logger.warning("reporting_service: failed to clean temp file %s", tmp_path)

    async def _fetch_report_row(self, inspection_id: uuid.UUID) -> Optional[ReportORM]:
        stmt = select(ReportORM).where(ReportORM.inspection_id == inspection_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def _upsert_report_row(
        self, input: ReportGenerationInput, pdf_path: str
    ) -> ReportORM:
        existing = await self._fetch_report_row(input.inspection_id)
        now = datetime.now(timezone.utc)

        if existing is not None:
            existing.case_id = input.case_id
            existing.pdf_path = pdf_path
            existing.verdict = input.judge.verdict.value
            existing.fraud_score = input.policy.fraud_score
            existing.confidence_score = input.policy.confidence_score
            existing.fraud_category = input.policy.fraud_category
            existing.recommended_action = input.policy.recommended_action.value
            existing.generated_at = now
            await self._session.flush()
            await self._session.refresh(existing)
            return existing

        new_row = ReportORM(
            id=uuid.uuid4(),
            inspection_id=input.inspection_id,
            case_id=input.case_id,
            pdf_path=pdf_path,
            verdict=input.judge.verdict.value,
            fraud_score=input.policy.fraud_score,
            confidence_score=input.policy.confidence_score,
            fraud_category=input.policy.fraud_category,
            recommended_action=input.policy.recommended_action.value,
            generated_at=now,
        )
        self._session.add(new_row)
        await self._session.flush()
        await self._session.refresh(new_row)
        return new_row

    @staticmethod
    def _to_metadata(row: ReportORM) -> ReportMetadata:
        return ReportMetadata(
            reportId=row.id,
            inspectionId=row.inspection_id,
            caseId=row.case_id,
            generatedAt=row.generated_at,
            pdfPath=row.pdf_path,
            verdict=Verdict(row.verdict),
            fraudScore=row.fraud_score,
            confidenceScore=row.confidence_score,
            fraudCategory=row.fraud_category,
            recommendedAction=RecommendedAction(row.recommended_action),
        )


# ─────────────────────────────────────────────
# Factory (for FastAPI dependency injection)
# ─────────────────────────────────────────────


def get_reporting_service(session: AsyncSession) -> ReportingService:
    """FastAPI dependency factory — wire via `Depends(get_reporting_service)`
    in routers/reports.py using an `AsyncSession = Depends(get_db_session)`."""
    return ReportingService(session=session)