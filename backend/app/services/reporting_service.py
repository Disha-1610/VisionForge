# backend/app/services/reporting_service.py
"""
Reporting Service — Industrial Hardware Audit PDF Generation (Disha, W4 D2).

Generates professional, enterprise-grade PDF audit reports for hardware inspections
using ReportLab. Includes case metadata, color-coded verdict banners, AI root-cause
forensic analyses, multi-agent evidence breakdown tables, and regulatory sign-off blocks.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import HRFlowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core.config import settings

logger = logging.getLogger("app.services.reporting_service")


class ReportingService:
    """Enterprise PDF report generator for VisionForge AI inspections."""

    def __init__(self, reports_dir: str | None = None) -> None:
        self.reports_dir = Path(reports_dir or settings.REPORTS_DIR)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self._setup_styles()

    def _setup_styles(self) -> None:
        self.styles = getSampleStyleSheet()

        self.style_title = ParagraphStyle(
            "DocTitle",
            parent=self.styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            textColor=colors.HexColor("#0f172a"),
        )
        self.style_subtitle = ParagraphStyle(
            "DocSubtitle",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#64748b"),
        )
        self.style_section_heading = ParagraphStyle(
            "SectionHeading",
            parent=self.styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=16,
            textColor=colors.HexColor("#1e293b"),
            spaceBefore=10,
            spaceAfter=6,
        )
        self.style_body = ParagraphStyle(
            "Body",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#334155"),
        )
        self.style_callout = ParagraphStyle(
            "Callout",
            parent=self.styles["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=9,
            leading=14,
            textColor=colors.HexColor("#1e293b"),
        )
        self.style_table_header = ParagraphStyle(
            "TableHeader",
            parent=self.styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=colors.white,
        )
        self.style_table_cell = ParagraphStyle(
            "TableCell",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#1e293b"),
        )

    def generate_pdf_report(
        self,
        *,
        case_number: str,
        inspection_id: UUID,
        vendor_name: str,
        location: str,
        part_code: str,
        product_type: str = "PCB Component",
        verdict: str = "accept",
        policy_action: str = "accept",
        fraud_score: float = 0.0,
        confidence: float = 95.0,
        fraud_category: str = "clean",
        root_cause: str = "Component conforms to golden reference specifications.",
        authenticity_score: float | None = 0.95,
        reference_similarity: float | None = 0.98,
        evidence_items: list[dict[str, Any]] | None = None,
        created_at: datetime | None = None,
    ) -> str:
        """
        Builds a multi-page or single-page PDF document and saves it to disk.
        Returns the saved file path string.
        """
        filename = f"{case_number}.pdf"
        output_path = self.reports_dir / filename

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=letter,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36,
        )

        story: list[Any] = []

        # 1. Header Banner
        header_text = (
            "<b>VISIONFORGE AI</b> &nbsp;|&nbsp; "
            "<font color='#64748b'>DEFENSE-GRADE HARDWARE AUDIT SYSTEM</font>"
        )
        story.append(Paragraph(header_text, self.style_title))
        timestamp_str = (created_at or datetime.now(timezone.utc)).strftime("%Y-%m-%d %H:%M:%S UTC")
        story.append(
            Paragraph(f"Inspection ID: {inspection_id} &nbsp;•&nbsp; Generated: {timestamp_str}", self.style_subtitle)
        )
        story.append(Spacer(1, 12))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0284c7"), spaceAfter=14))

        # 2. Case Metadata Table
        meta_data = [
            [
                Paragraph("<b>Case Number:</b>", self.style_body),
                Paragraph(case_number, self.style_body),
                Paragraph("<b>Vendor / Supplier:</b>", self.style_body),
                Paragraph(vendor_name, self.style_body),
            ],
            [
                Paragraph("<b>Part Code:</b>", self.style_body),
                Paragraph(part_code, self.style_body),
                Paragraph("<b>Audit Location:</b>", self.style_body),
                Paragraph(location, self.style_body),
            ],
            [
                Paragraph("<b>Product Type:</b>", self.style_body),
                Paragraph(product_type, self.style_body),
                Paragraph("<b>Reference Similarity:</b>", self.style_body),
                Paragraph(f"{reference_similarity * 100:.1f}%" if reference_similarity is not None else "N/A", self.style_body),
            ],
        ]
        meta_table = Table(meta_data, colWidths=[110, 160, 110, 160])
        meta_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ])
        )
        story.append(meta_table)
        story.append(Spacer(1, 14))

        # 3. Verdict & Policy Action Banner
        verdict_upper = verdict.upper()
        action_upper = policy_action.upper().replace("_", " ")

        if verdict_upper in ("REJECT", "QUARANTINE") or policy_action == "quarantine":
            banner_bg = colors.HexColor("#fee2e2")
            banner_border = colors.HexColor("#ef4444")
            banner_text_color = "#b91c1c"
        elif verdict_upper in ("REVIEW", "VENDOR_VERIFICATION") or policy_action == "vendor_verification":
            banner_bg = colors.HexColor("#fef3c7")
            banner_border = colors.HexColor("#f59e0b")
            banner_text_color = "#b45309"
        elif policy_action == "retake":
            banner_bg = colors.HexColor("#e0f2fe")
            banner_border = colors.HexColor("#0284c7")
            banner_text_color = "#0369a1"
        else:
            banner_bg = colors.HexColor("#dcfce7")
            banner_border = colors.HexColor("#10b981")
            banner_text_color = "#15803d"

        verdict_style = ParagraphStyle(
            "VerdictStyle",
            parent=self.styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            textColor=colors.HexColor(banner_text_color),
            alignment=1,  # Centered
        )

        banner_content = [
            [
                Paragraph(
                    f"VERDICT: {verdict_upper} &nbsp;&nbsp;|&nbsp;&nbsp; POLICY ACTION: {action_upper}<br/>"
                    f"<font size=9>Fraud Risk Score: {fraud_score:.1f}% &nbsp;•&nbsp; AI Confidence: {confidence:.1f}% &nbsp;•&nbsp; Category: {fraud_category.upper()}</font>",
                    verdict_style,
                )
            ]
        ]
        banner_table = Table(banner_content, colWidths=[540])
        banner_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), banner_bg),
                ("BOX", (0, 0), (-1, -1), 1.5, banner_border),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ])
        )
        story.append(banner_table)
        story.append(Spacer(1, 14))

        # 4. Root Cause Analysis
        story.append(Paragraph("AI JUDGE FORENSIC ROOT-CAUSE ANALYSIS", self.style_section_heading))
        root_cause_table = Table(
            [[Paragraph(f"<b>Findings & Justification:</b><br/>{root_cause}", self.style_callout)]],
            colWidths=[540],
        )
        root_cause_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
                ("LINELEFT", (0, 0), (0, 0), 3, colors.HexColor("#3b82f6")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ])
        )
        story.append(root_cause_table)
        story.append(Spacer(1, 14))

        # 5. Multi-Agent Evidence Table
        story.append(Paragraph("INSPECTION EVIDENCE FINDINGS", self.style_section_heading))
        table_rows: list[list[Any]] = [
            [
                Paragraph("Agent", self.style_table_header),
                Paragraph("Region (ROI)", self.style_table_header),
                Paragraph("Status", self.style_table_header),
                Paragraph("Conf.", self.style_table_header),
                Paragraph("Technical Findings", self.style_table_header),
            ]
        ]

        items = evidence_items or []
        if not items:
            table_rows.append([
                Paragraph("System", self.style_table_cell),
                Paragraph("All", self.style_table_cell),
                Paragraph("PASS", self.style_table_cell),
                Paragraph("100%", self.style_table_cell),
                Paragraph("No critical evidence anomalies logged during inspection.", self.style_table_cell),
            ])
        else:
            for item in items:
                agent = str(item.get("agent_type", item.get("agent_name", "agent"))).upper()
                roi = str(item.get("roi_id", item.get("roi", "board")))
                status_text = "FAILED" if item.get("failed") else ("DEFECT" if item.get("has_defect", False) else "PASS")
                conf_val = float(item.get("confidence", 0.9))
                conf_str = f"{conf_val * 100:.0f}%" if conf_val <= 1.0 else f"{conf_val:.0f}%"
                explanation = str(item.get("explanation", item.get("evidence_summary", "No details")))

                table_rows.append([
                    Paragraph(agent, self.style_table_cell),
                    Paragraph(roi, self.style_table_cell),
                    Paragraph(status_text, self.style_table_cell),
                    Paragraph(conf_str, self.style_table_cell),
                    Paragraph(explanation, self.style_table_cell),
                ])

        evidence_table = Table(table_rows, colWidths=[70, 90, 50, 45, 285])
        evidence_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ])
        )
        story.append(evidence_table)
        story.append(Spacer(1, 18))

        # 6. Regulatory Sign-Off Block
        signoff_data = [
            [
                Paragraph("<b>Auditing Quality Inspector:</b>", self.style_body),
                Paragraph("__________________________", self.style_body),
                Paragraph("<b>Date Signed:</b>", self.style_body),
                Paragraph("____________________", self.style_body),
            ],
            [
                Paragraph("<b>Operations Lead Review:</b>", self.style_body),
                Paragraph("__________________________", self.style_body),
                Paragraph("<b>Action Applied:</b>", self.style_body),
                Paragraph(f"[ {action_upper} ]", self.style_body),
            ],
        ]
        signoff_table = Table(signoff_data, colWidths=[140, 150, 110, 140])
        signoff_table.setStyle(
            TableStyle([
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ])
        )
        story.append(KeepTogether([
            Paragraph("AUDIT VALIDATION & CHAIN OF CUSTODY SIGN-OFF", self.style_section_heading),
            signoff_table,
        ]))

        # Build document
        doc.build(story)
        logger.info("PDF inspection report generated: %s (case: %s)", output_path, case_number)
        return str(output_path)


reporting_service = ReportingService()
