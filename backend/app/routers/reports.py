from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.report import ReportResponse
from app.services.reporting_service import ReportingService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/reports",
    tags=["Reports"],
)


# ---------------------------------------------------------------------------
# API models
# ---------------------------------------------------------------------------


class ReportListItem(BaseModel):
    """Compact representation used by the report archive."""

    model_config = {"from_attributes": True}

    id: UUID
    case_id: str
    inspection_id: UUID

    created_at: object

    vendor_id: UUID | None = None
    vendor_name: str | None = None
    location: str | None = None

    product_type: str

    verdict: str
    fraud_score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=100)
    fraud_category: str

    recommended_action: str


class PaginatedReportsResponse(BaseModel):
    """Paginated report archive response."""

    items: list[ReportListItem]

    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)

    total: int = Field(ge=0)
    total_pages: int = Field(ge=0)

    has_next: bool
    has_previous: bool


class ReportPdf:
    """Internal representation of a generated PDF."""

    def __init__(
        self,
        *,
        content: bytes,
        filename: str,
        media_type: str = "application/pdf",
    ) -> None:
        self.content = content
        self.filename = filename
        self.media_type = media_type


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def get_reporting_service(
    db: Annotated[object, Depends(get_db)],
) -> ReportingService:
    """
    Construct the reporting service for the current request.

    The service owns report retrieval and generation logic. The router only
    coordinates HTTP concerns and dependency injection.
    """
    return ReportingService(db=db)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_date_range(
    date_from: object | None,
    date_to: object | None,
) -> None:
    """Reject an inverted report date range before calling the service."""
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="date_from must be earlier than or equal to date_to",
        )


def _map_service_error(
    exc: Exception,
    *,
    operation: str,
) -> HTTPException:
    """
    Convert known service failures into safe HTTP errors.

    Internal exception details are logged but are never returned directly to
    clients.
    """
    logger.exception(
        "Report router operation failed",
        extra={
            "operation": operation,
            "error_type": type(exc).__name__,
        },
    )

    status_code = getattr(exc, "status_code", None)

    if isinstance(status_code, int) and 400 <= status_code <= 599:
        detail = getattr(exc, "detail", None)

        if isinstance(detail, str) and detail.strip():
            return HTTPException(
                status_code=status_code,
                detail=detail,
            )

    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Unable to process the report request",
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=PaginatedReportsResponse,
    status_code=status.HTTP_200_OK,
    summary="List generated reports",
    description=(
        "Returns the authenticated user's report archive. Administrators "
        "may receive the complete report set according to the reporting "
        "service's RBAC rules."
    ),
)
async def list_reports(
    current_user: Annotated[User, Depends(get_current_user)],
    reporting_service: Annotated[
        ReportingService,
        Depends(get_reporting_service),
    ],
    date_from: Annotated[
        object | None,
        Query(
            default=None,
            description="Inclusive lower bound for report creation time.",
        ),
    ] = None,
    date_to: Annotated[
        object | None,
        Query(
            default=None,
            description="Inclusive upper bound for report creation time.",
        ),
    ] = None,
    vendor_id: Annotated[
        UUID | None,
        Query(
            default=None,
            description="Filter reports by vendor.",
        ),
    ] = None,
    location: Annotated[
        str | None,
        Query(
            default=None,
            min_length=1,
            max_length=255,
            description="Filter reports by inspection location.",
        ),
    ] = None,
    verdict: Annotated[
        str | None,
        Query(
            default=None,
            min_length=1,
            max_length=32,
            description="Filter by final verdict.",
        ),
    ] = None,
    fraud_category: Annotated[
        str | None,
        Query(
            default=None,
            min_length=1,
            max_length=100,
            description="Filter by fraud category.",
        ),
    ] = None,
    page: Annotated[
        int,
        Query(
            default=1,
            ge=1,
            le=10_000,
            description="1-based page number.",
        ),
    ] = 1,
    page_size: Annotated[
        int,
        Query(
            default=20,
            ge=1,
            le=100,
            description="Number of reports per page.",
        ),
    ] = 20,
) -> PaginatedReportsResponse:
    """
    Return a filtered, paginated report archive.

    Authorization filtering remains in the service layer so that every
    access path enforces the same operator/admin visibility rules.
    """
    _validate_date_range(date_from, date_to)

    normalized_location = location.strip() if location else None
    normalized_verdict = verdict.strip().upper() if verdict else None
    normalized_category = fraud_category.strip() if fraud_category else None

    filters = {
        "date_from": date_from,
        "date_to": date_to,
        "vendor_id": vendor_id,
        "location": normalized_location,
        "verdict": normalized_verdict,
        "fraud_category": normalized_category,
        "page": page,
        "page_size": page_size,
    }

    try:
        result = await reporting_service.list_reports(
            filters=filters,
            current_user=current_user,
        )

        return PaginatedReportsResponse.model_validate(result)

    except HTTPException:
        raise
    except Exception as exc:
        raise _map_service_error(
            exc,
            operation="list_reports",
        ) from exc


@router.get(
    "/{report_id}",
    response_model=ReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a report",
    description="Returns the complete explainable report for a specific case.",
)
async def get_report(
    report_id: Annotated[
        UUID,
        Path(
            description="Unique report identifier.",
        ),
    ],
    current_user: Annotated[User, Depends(get_current_user)],
    reporting_service: Annotated[
        ReportingService,
        Depends(get_reporting_service),
    ],
) -> ReportResponse:
    """
    Return one complete report.

    The reporting service performs ownership/RBAC checks and retrieves the
    complete evidence-backed report.
    """
    try:
        report = await reporting_service.get_report(
            report_id=report_id,
            current_user_id=current_user.id,
        )

        if report is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not found",
            )

        return ReportResponse.model_validate(report)

    except HTTPException:
        raise
    except Exception as exc:
        raise _map_service_error(
            exc,
            operation="get_report",
        ) from exc


@router.get(
    "/{report_id}/pdf",
    response_class=Response,
    status_code=status.HTTP_200_OK,
    summary="Download a report as PDF",
    description="Generates or retrieves the explainable PDF report for a case.",
)
async def download_report_pdf(
    report_id: Annotated[
        UUID,
        Path(
            description="Unique report identifier.",
        ),
    ],
    current_user: Annotated[User, Depends(get_current_user)],
    reporting_service: Annotated[
        ReportingService,
        Depends(get_reporting_service,
        ),
    ],
) -> Response:
    """
    Return the report PDF as an HTTP attachment.

    PDF generation is delegated entirely to ReportingService/ReportLab.
    """
    try:
        pdf = await reporting_service.get_report_pdf(
            report_id=report_id,
            current_user_id=current_user.id,
        )

        if pdf is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not found",
            )

        if not pdf.content:
            logger.error(
                "Reporting service returned an empty PDF",
                extra={"report_id": str(report_id)},
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Generated report is empty",
            )

        filename = pdf.filename.strip()

        if not filename:
            filename = f"visionforge-report-{report_id}.pdf"

        if not filename.lower().endswith(".pdf"):
            filename = f"{filename}.pdf"

        safe_filename = (
            filename.replace("\r", "")
            .replace("\n", "")
            .replace('"', "")
        )

        return Response(
            content=pdf.content,
            media_type=pdf.media_type or "application/pdf",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{safe_filename}"'
                ),
                "Content-Length": str(len(pdf.content)),
                "Cache-Control": "private, no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    except HTTPException:
        raise
    except Exception as exc:
        raise _map_service_error(
            exc,
            operation="download_report_pdf",
        ) from exc